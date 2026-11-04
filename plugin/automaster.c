/*
 * author: Taehong Kim
 * email: peppy0510@hotmail.com
 *
 * Copied from PyWinAudio (plugin/automaster.c at 38b1f61) for LOUD.
 * Only METER_NAME differs: keep the rest in sync with PyWinAudio.
 *
 * PyWinAudio Auto Master: broadcast-style VST2 processor, hosted by Equalizer APO in audiodg.
 * AGC, stereo correction, lookahead peak limiter. No editor: the rack shows the parameters.
 * The VST2 ABI (AEffect, dispatcher opcodes) is written out here as in source/vsthost.py, no SDK.
 *
 * AGC: BS.1770 K-weighted input loudness (~3 s mean) moves the gain slowly toward Target.
 * Taken before the gain, so no feedback. Below -45 LUFS (50 ms) measuring and gain hold;
 * more than 10 dB under the long mean (gaps, fades) both follow 10x slower.
 *
 * Limiter: 5 ms lookahead. Window minimum of the needed gain, smoothed by a box average of the
 * same length so it lands on the peak exactly; slower separate release. Latency in initialDelay.
 *   Drive: gain into the limiter (0..+30 dB).
 *   Smooth: second release, a floor of the reduction followed in 0.1 s, held 0.25 s after the
 *     last deepening, then rising at 20 dB/s.
 *   Attack: ramp length (0.5..5 ms). Latency stays 5 ms; a shorter ramp delays the gain instead.
 *
 * Stereo (between AGC and limiter), input averaged over ~5 s:
 *   Balance: a constant L/R offset is split over both sides (up to +-3 dB each).
 *   Width Limit: S cut when S/M exceeds Max Width (up to 6 dB). Never widens.
 *   Bass Mono: S removed below 120 Hz.
 *   Mono Wide: fake S from M through velvet noise (25 ms, 1500 pulses/s, decaying), added to L
 *     and subtracted from R, so L+R is untouched and mono has no comb (Alary, Politis, Valimaki,
 *     DAFx-17). Nothing below 150 Hz; ducked on transients.
 *     Three LR4 bands above 150 Hz (150-600 Hz, 600 Hz-3 kHz, 3 kHz up), each detected and
 *     filled on its own; target = Wide Target -5 dB, +0 dB, +Air (-6..+6 dB). Detection ends at
 *     10 kHz: MP3 side residue up there would make mono read as stereo.
 *     Fills only the missing S energy (target minus present S): wide input passes unchanged.
 * Measuring stops in silence, as in the AGC.
 *
 * Meters: each block, every stage's correction goes to shared memory METER_NAME. Global name and
 * a world DACL: the plugin runs in audiodg (session 0, LocalService), the rack in the desktop
 * session. One slot per instance; the rack reads the most recently active one.
 */

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <xmmintrin.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <sddl.h>

#define MAGIC 0x56737450 /* 'VstP' */
#define UNIQUE_ID 0x5077414D /* 'PwAM' */
#define VERSION 100

#define EFF_OPEN 0
#define EFF_CLOSE 1
#define EFF_SET_PROGRAM 2
#define EFF_GET_PROGRAM 3
#define EFF_GET_PROGRAM_NAME 5
#define EFF_GET_PARAM_LABEL 6
#define EFF_GET_PARAM_DISPLAY 7
#define EFF_GET_PARAM_NAME 8
#define EFF_SET_SAMPLE_RATE 10
#define EFF_SET_BLOCK_SIZE 11
#define EFF_MAINS_CHANGED 12
#define EFF_GET_PLUG_CATEGORY 35
#define EFF_GET_EFFECT_NAME 45
#define EFF_GET_VENDOR_STRING 47
#define EFF_GET_PRODUCT_STRING 48
#define EFF_GET_VENDOR_VERSION 49
#define EFF_CAN_DO 51
#define EFF_GET_PARAMETER_PROPERTIES 56
#define EFF_GET_VST_VERSION 58

#define PARAM_IS_SWITCH (1 << 0)
#define PARAM_SUPPORTS_DISPLAY_CATEGORY (1 << 5)

/* VST2 VstParameterProperties: lets the host see sections and switches */
typedef struct {
    float stepFloat, smallStepFloat, largeStepFloat;
    char label[64];
    int32_t flags;
    int32_t minInteger, maxInteger, stepInteger, largeStepInteger;
    char shortLabel[8];
    int16_t displayIndex;
    int16_t category;
    int16_t numParametersInCategory;
    int16_t reserved;
    char categoryLabel[24];
    char future[16];
} ParameterProperties;

#define FLAG_CAN_REPLACING (1 << 4)
#define CATEGORY_MASTERING 4

#define MASTER_VERSION 1

typedef struct AEffect AEffect;
typedef intptr_t (*AudioMaster)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
typedef intptr_t (*Dispatcher)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
typedef void (*Process)(AEffect *, float **, float **, int32_t);
typedef void (*SetParameter)(AEffect *, int32_t, float);
typedef float (*GetParameter)(AEffect *, int32_t);

struct AEffect {
    int32_t magic;
    Dispatcher dispatcher;
    Process process;
    SetParameter setParameter;
    GetParameter getParameter;
    int32_t numPrograms;
    int32_t numParams;
    int32_t numInputs;
    int32_t numOutputs;
    int32_t flags;
    intptr_t resvd1;
    intptr_t resvd2;
    int32_t initialDelay;
    int32_t realQualities;
    int32_t offQualities;
    float ioRatio;
    void *object;
    void *user;
    int32_t uniqueID;
    int32_t version;
    Process processReplacing;
    void *processDoubleReplacing;
    char future[56];
};

/* ------------------------------------------------------------ parameters */

enum {
    P_AGC,
    P_TARGET,
    P_MAX_GAIN,
    P_SPEED,
    P_BALANCE,
    P_PHASE_FIX,
    P_WIDTH_LIMIT,
    P_WIDTH,
    P_BASS_MONO,
    P_MONO_WIDE,
    P_WIDE_AMOUNT,
    P_AIR,
    P_LIMITER,
    P_CEILING,
    P_DRIVE,
    P_SMOOTH,
    P_ATTACK,
    PARAM_COUNT
};

static const char *PARAM_NAMES[PARAM_COUNT] = {
    "AGC", "Target", "Max Gain", "Speed", "Balance", "Phase Fix", "Width Limit", "Max Width",
    "Bass Mono", "Mono Wide", "Wide Target", "Air", "Limiter", "Ceiling",
    "Drive", "Smooth", "Attack"
};
/* sections: 1 AGC, 2 Stereo, 3 Limiter; the rack draws a rule between them */
static const int16_t PARAM_CATEGORIES[PARAM_COUNT] = {1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3};
static const char *CATEGORY_LABELS[4] = {"", "AGC", "Stereo", "Limiter"};
static const char *PARAM_LABELS[PARAM_COUNT] = {
    "", "LUFS", "dB", "s", "", "", "", "S/M dB", "", "", "S/M dB", "dB", "", "dB", "dB", "", "ms"
};
/* defaults: AGC on, -16 LUFS, max +9 dB, ~3 s, Max Width -6 dB, Wide Target -7.5 dB, Air +2 dB,
 * Ceiling -1 dBFS, Drive 0 dB, Smooth off, Attack 1 ms; other switches on */
static const float PARAM_DEFAULTS[PARAM_COUNT] = {
    1.0f, 0.5f, 0.5f, 0.5f, 1.0f, 1.0f, 1.0f, 12.0f / 14.0f, 1.0f, 1.0f, 10.5f / 18.0f, 8.0f / 12.0f,
    1.0f, 5.0f / 6.0f, 0.0f, 0.0f, 1.0f / 9.0f
};

static int is_switch(int32_t index)
{
    return index == P_AGC || index == P_BALANCE || index == P_PHASE_FIX || index == P_WIDTH_LIMIT ||
           index == P_BASS_MONO || index == P_MONO_WIDE || index == P_LIMITER || index == P_SMOOTH;
}

#define TARGET_LOW -24.0
#define TARGET_HIGH -8.0
#define MAX_GAIN_HIGH 18.0
#define MIN_GAIN -12.0
#define CEILING_LOW -6.0
#define GATE_LUFS -45.0
#define MEASURE_TIME 3.0
#define GATE_TIME 0.05
/* gaps and fades (this far under the long mean) follow 10x slower, not frozen,
 * or a song that turns much quieter is never caught up */
#define RELATIVE_GATE 10.0
#define RELATIVE_SLOW 0.1
#define STEREO_TIME 5.0
#define STEREO_FOLLOW 2.0
#define BALANCE_LIMIT 6.0      /* L/R difference corrected, half per side (+-3 dB) */
#define SIDE_LIMIT 6.0
#define WIDTH_LOW -18.0
#define WIDTH_HIGH -4.0
#define MONO_SOURCE -30.0      /* S this far under M: mono source */
#define BASS_MONO_HZ 120.0
#define WIDE_LOW -18.0
#define WIDE_HIGH 0.0
/* mono wide: three bands above 150 Hz, each detected and filled; less in the low mids,
 * Air sets the highs; detection ends at 10 kHz, above where MP3 cuts off */
#define BANDS 3
static const double BAND_EDGES[BANDS + 1] = {150.0, 600.0, 3000.0, 10000.0};
/* the highs take Air instead (last entry unused) */
static const double BAND_OFFSET[BANDS] = {-5.0, 0.0, 0.0};
#define AIR_LOW -6.0
#define AIR_HIGH 6.0
#define WIDE_HZ 150.0
#define MAX_WIDE_DELAY 8192    /* 42 ms at 192 kHz */
#define VELVET_LENGTH 0.025      /* s */
#define VELVET_DENSITY 1500.0    /* pulses per s */
#define VELVET_DECAY -30.0       /* last pulse level (dB) */
#define MAX_PULSES 64
#define TRANSIENT_RATIO 3.0      /* fast/slow envelope ratio (9.5 dB) above which it is a transient */
#define TRANSIENT_DUCK 0.4       /* fake S scale during transients */
#define FAST_TIME 0.001
#define SLOW_TIME 0.05
#define DUCK_RELEASE 0.03
/* fill meter mean; includes transient ducking (band energy weighted) */
#define FILL_METER_TIME 1.0
/* phase fix: L/R 150 Hz-4 kHz cross-correlation over +-2 ms every 0.25 s (~1 s smoothing);
 * peak under -0.5 flips R (back above -0.2); a nonzero lag >= 0.85 and 0.08 over lag 0
 * three times in a row delays the leading side; changes fade over 20 ms */
#define PHASE_LOW_HZ 150.0
#define PHASE_HIGH_HZ 4000.0
#define PHASE_MAX_LAG 0.002
#define PHASE_WINDOW 8192
#define PHASE_EVERY 0.25
#define PHASE_SMOOTH 0.3
#define PHASE_FLIP -0.5
#define PHASE_UNFLIP -0.2
#define PHASE_MATCH 0.85
#define PHASE_GAIN 0.08
#define PHASE_STABLE 3
#define PHASE_FADE 0.02
#define MAX_LAG 512
#define LOOKAHEAD_TIME 0.005
#define RELEASE_TIME 0.08
#define MAX_LOOKAHEAD 1024
#define DRIVE_HIGH 30.0
#define SMOOTH_ATTACK 0.1      /* s, while the floor deepens */
#define SMOOTH_RATE 20.0       /* dB/s, while the floor releases */
#define ATTACK_LOW 0.0005
#define SMOOTH_HOLD 0.25       /* s held after the last deepening before release */

/* ------------------------------------------------------------ meters (shared memory) */

#define METER_MAGIC 0x4D415750 /* 'PWAM' */
/* bump with the slot layout, and in METER_NAME: an old DLL's mapping
 * under the same name is smaller and would overflow */
#define METER_VERSION 4
/* own name: kept off the PyWinAudio rack's meters and A/B bypass */
#define METER_NAME L"PyMusicPlayerAutoMaster.v4"
#define METER_SLOTS 8

typedef struct {
    volatile LONG64 owner;  /* owning instance (pointer value), 0 = free */
    volatile LONG64 tick;   /* GetTickCount64 of the last processed block */
    float agc_db;           /* current AGC gain */
    float balance_db;       /* L/R correction (+ lowers L) */
    float side_db;          /* width cut (<= 0) */
    float fill_db;          /* fake S actually mixed (dB re M, 1 s mean, -120 if none) */
    float limiter_db;       /* deepest limiter cut this block (<= 0) */
    float loudness;         /* input loudness (LUFS) */
    int32_t sounding;
    int32_t phase_flip;     /* 1 while R is inverted */
    float fill_band_db[3];  /* fake S mixed per band (150-600 Hz, 600 Hz-3 kHz, 3 kHz up) */
    float phase_delay_ms;   /* alignment delay (+ delays L, - delays R) */
    float band_width_db[3]; /* input width per band (S/M dB, detection mean) */
    float band_target_db[3];/* target width per band (Wide Target + band offset) */
} MeterSlot;

typedef struct {
    uint32_t magic;
    uint32_t version;
    /* written by the rack: nonzero = A/B, dry signal at the same gain and delay; switched here
     * since changing the config line recreates the plugin and resets its adaptation */
    volatile LONG bypass;
    uint32_t reserved;
    MeterSlot slots[METER_SLOTS];
} MeterBlock;

static HANDLE meter_mapping = NULL;
static MeterBlock *meter_block = NULL;

static MeterBlock *open_meters(void)
{
    if (meter_block != NULL)
        return meter_block;
    SECURITY_ATTRIBUTES attributes = {sizeof(attributes), NULL, FALSE};
    PSECURITY_DESCRIPTOR descriptor = NULL;
    /* full access for everyone (the rack only reads) */
    if (ConvertStringSecurityDescriptorToSecurityDescriptorW(L"D:(A;;GA;;;WD)", SDDL_REVISION_1,
                                                              &descriptor, NULL))
        attributes.lpSecurityDescriptor = descriptor;
    HANDLE mapping = CreateFileMappingW(INVALID_HANDLE_VALUE, &attributes, PAGE_READWRITE, 0,
                                        sizeof(MeterBlock), L"Global\\" METER_NAME);
    if (mapping == NULL)
        mapping = CreateFileMappingW(INVALID_HANDLE_VALUE, &attributes, PAGE_READWRITE, 0,
                                     sizeof(MeterBlock), L"Local\\" METER_NAME);
    if (descriptor != NULL)
        LocalFree(descriptor);
    if (mapping == NULL)
        return NULL;
    MeterBlock *block = (MeterBlock *)MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0,
                                                    sizeof(MeterBlock));
    if (block == NULL) {
        CloseHandle(mapping);
        return NULL;
    }
    block->magic = METER_MAGIC;
    block->version = METER_VERSION;
    meter_mapping = mapping;
    meter_block = block;
    return block;
}

static MeterSlot *claim_slot(void *owner)
{
    MeterBlock *block = open_meters();
    if (block == NULL)
        return NULL;
    ULONGLONG now = GetTickCount64();
    for (int index = 0; index < METER_SLOTS; index++) {
        MeterSlot *slot = &block->slots[index];
        LONG64 current = slot->owner;
        /* take a free slot or one idle over 10 s (left by a dead process) */
        if (current == 0 || now - (ULONGLONG)slot->tick > 10000) {
            if (InterlockedCompareExchange64(&slot->owner, (LONG64)(intptr_t)owner, current) ==
                current) {
                slot->tick = 0;
                return slot;
            }
        }
    }
    return NULL;
}

/* ------------------------------------------------------------ state */

typedef struct {
    double b0, b1, b2, a1, a2;
    double z1[2], z2[2];
} Biquad;

typedef struct {
    AEffect effect;
    AudioMaster master;
    float params[PARAM_COUNT];
    double rate;

    Biquad shelf, highpass;
    double power;          /* K-weighted mean square (both channels) */
    double power_coef;
    double momentary;      /* 50 ms mean square, for gating */
    double momentary_coef;
    double gain_db;        /* current AGC gain */

    double left_power, right_power, mid_power, side_power;
    double stereo_coef, follow_coef;
    double balance_db;     /* + when L is louder: L down by half, R up by half */
    double side_db;        /* gain on S */
    Biquad bass;           /* 120 Hz highpass on S */
    Biquad wide_highpass;  /* 150 Hz highpass on fake S */
    /* mono detection: per band two highpasses, two lowpasses (LR4; 0 = M, 1 = S) */
    Biquad detect[BANDS][4];
    double detect_mid[BANDS], detect_side[BANDS];
    /* crossover splitting fake S at 600 Hz and 3 kHz (LR4 = two biquads each) */
    Biquad split_low[2], split_rest[2], split_mid[2], split_high[2];
    float wide_delay[MAX_WIDE_DELAY];
    int wide_head;
    int pulse_count;
    int pulse_at[MAX_PULSES];      /* pulse positions (samples) */
    float pulse_gain[MAX_PULSES];  /* sign * level, unit energy */
    double fast_env, slow_env, duck;
    double fast_coef, slow_coef, duck_coef;
    double wide_mix[BANDS];  /* fake S mixed per band (ratio to M) */
    /* fill meter: (wide_mix * duck)^2 weighted by band M energy, sum and weight */
    double fill_power, fill_weight;
    double fill_band_power[BANDS], fill_band_weight[BANDS];
    double fill_coef;

    /* phase fix */
    Biquad phase_band[2];        /* detection 150 Hz highpass, 4 kHz lowpass (0 = L, 1 = R) */
    float phase_l[PHASE_WINDOW], phase_r[PHASE_WINDOW];
    float flat_l[PHASE_WINDOW], flat_r[PHASE_WINDOW];  /* window unrolled for measuring (no modulo) */
    int phase_head, phase_tick, phase_every, max_lag;
    double phase_score[2 * MAX_LAG + 1];
    int flipped;
    double flip_gain, fade_step;
    int lag, candidate, candidate_count;  /* current lag, next candidate and its run count */
    int fade_from;                        /* previous lag while fading */
    double fade;                          /* 0 -> 1 */
    float input_l[2 * MAX_LAG], input_r[2 * MAX_LAG];
    int input_head;

    int lookahead;         /* limiter lookahead (samples) */
    float delay[2][MAX_LOOKAHEAD];
    float raw_delay[2][MAX_LOOKAHEAD];  /* A/B dry signal (AGC gain only, level matched) */
    double bypass_mix;                  /* 0 = processed, 1 = dry */
    float wanted[MAX_LOOKAHEAD];  /* needed gain per sample */
    float held[MAX_LOOKAHEAD];    /* window minimum (after release) */
    int head;
    double held_sum;
    double release;        /* current release gain */
    double floor_db;       /* Smooth floor (dB, <= 0) */
    double floor_coef, floor_step;
    int floor_hold, hold_length;
    int attack;                   /* ramp length (samples), <= lookahead */
    float late_gain[MAX_LOOKAHEAD];  /* a short ramp delays the gain by lookahead - attack */
    MeterSlot *meter;      /* meter slot (NULL if none) */
    double release_coef;
} AutoMaster;

static double get_speed_time(float value)
{
    /* 0 -> 10 s (slow), 1 -> 1 s (fast), ~3 s in the middle */
    return 10.0 * pow(0.1, value);
}

static double get_target(const AutoMaster *self)
{
    return TARGET_LOW + (TARGET_HIGH - TARGET_LOW) * self->params[P_TARGET];
}

static double get_max_gain(const AutoMaster *self)
{
    return MAX_GAIN_HIGH * self->params[P_MAX_GAIN];
}

static double get_width(const AutoMaster *self)
{
    return WIDTH_LOW + (WIDTH_HIGH - WIDTH_LOW) * self->params[P_WIDTH];
}

static double get_wide_amount(const AutoMaster *self)
{
    return WIDE_LOW + (WIDE_HIGH - WIDE_LOW) * self->params[P_WIDE_AMOUNT];
}

static double get_air(const AutoMaster *self)
{
    return AIR_LOW + (AIR_HIGH - AIR_LOW) * self->params[P_AIR];
}

static double clamp(double value, double low, double high)
{
    return value < low ? low : value > high ? high : value;
}

static double get_ceiling(const AutoMaster *self)
{
    return CEILING_LOW * (1.0 - self->params[P_CEILING]);
}

static double get_drive(const AutoMaster *self)
{
    return DRIVE_HIGH * self->params[P_DRIVE];
}

static double get_attack(const AutoMaster *self)
{
    return ATTACK_LOW + (LOOKAHEAD_TIME - ATTACK_LOW) * self->params[P_ATTACK];
}

static int is_on(float value)
{
    return value >= 0.5f;
}

/* BS.1770 K-weighting: high shelf + RLB highpass, per sample rate */
static void set_filters(AutoMaster *self)
{
    double rate = self->rate;
    double f0 = 1681.974450955533, gain = 3.999843853973347, q = 0.7071752369554196;
    double k = tan(M_PI * f0 / rate);
    double vh = pow(10.0, gain / 20.0);
    double vb = pow(vh, 0.4996667741545416);
    double a0 = 1.0 + k / q + k * k;
    Biquad *b = &self->shelf;
    b->b0 = (vh + vb * k / q + k * k) / a0;
    b->b1 = 2.0 * (k * k - vh) / a0;
    b->b2 = (vh - vb * k / q + k * k) / a0;
    b->a1 = 2.0 * (k * k - 1.0) / a0;
    b->a2 = (1.0 - k / q + k * k) / a0;

    f0 = 38.13547087602444;
    q = 0.5003270373238773;
    k = tan(M_PI * f0 / rate);
    a0 = 1.0 + k / q + k * k;
    b = &self->highpass;
    b->b0 = 1.0;
    b->b1 = -2.0;
    b->b2 = 1.0;
    b->a1 = 2.0 * (k * k - 1.0) / a0;
    b->a2 = (1.0 - k / q + k * k) / a0;

    /* 2nd-order Butterworth highpass for bass mono (S only) */
    double w0 = 2.0 * M_PI * BASS_MONO_HZ / rate;
    double alpha = sin(w0) / (2.0 * 0.7071067811865476);
    double c = cos(w0);
    a0 = 1.0 + alpha;
    b = &self->bass;
    b->b0 = (1.0 + c) / 2.0 / a0;
    b->b1 = -(1.0 + c) / a0;
    b->b2 = (1.0 + c) / 2.0 / a0;
    b->a1 = -2.0 * c / a0;
    b->a2 = (1.0 - alpha) / a0;

    w0 = 2.0 * M_PI * WIDE_HZ / rate;
    alpha = sin(w0) / (2.0 * 0.7071067811865476);
    c = cos(w0);
    a0 = 1.0 + alpha;
    b = &self->wide_highpass;
    b->b0 = (1.0 + c) / 2.0 / a0;
    b->b1 = -(1.0 + c) / a0;
    b->b2 = (1.0 + c) / 2.0 / a0;
    b->a1 = -2.0 * c / a0;
    b->a2 = (1.0 - alpha) / a0;
}

static void set_pass(Biquad *b, double rate, double hz, int highpass)
{
    double w0 = 2.0 * M_PI * hz / rate;
    double alpha = sin(w0) / (2.0 * 0.7071067811865476);
    double c = cos(w0);
    double a0 = 1.0 + alpha;
    double k = highpass ? (1.0 + c) : (1.0 - c);
    b->b0 = k / 2.0 / a0;
    b->b1 = (highpass ? -k : k) / a0;
    b->b2 = k / 2.0 / a0;
    b->a1 = -2.0 * c / a0;
    b->a2 = (1.0 - alpha) / a0;
}

static double run_biquad(Biquad *b, int channel, double x)
{
    double y = b->b0 * x + b->z1[channel];
    b->z1[channel] = b->b1 * x - b->a1 * y + b->z2[channel];
    b->z2[channel] = b->b2 * x - b->a2 * y;
    return y;
}

/* smoothed +-max_lag cross-correlation; sets the flip and the lag to align */
static void estimate_phase(AutoMaster *self)
{
    int lags = self->max_lag;
    int count = PHASE_WINDOW - 2 * lags;
    int start = self->phase_head;  /* oldest sample */
    int tail = PHASE_WINDOW - start;
    memcpy(self->flat_l, self->phase_l + start, tail * sizeof(float));
    memcpy(self->flat_l + tail, self->phase_l, start * sizeof(float));
    memcpy(self->flat_r, self->phase_r + start, tail * sizeof(float));
    memcpy(self->flat_r + tail, self->phase_r, start * sizeof(float));
    const float *fl = self->flat_l + lags, *fr = self->flat_r + lags;
    double ll = 0.0, rr = 0.0;
    for (int i = 0; i < count; i++) {
        ll += (double)fl[i] * fl[i];
        rr += (double)fr[i] * fr[i];
    }
    if (ll < 1e-9 || rr < 1e-9)
        return;  /* silent: skip */
    double norm = 1.0 / sqrt(ll * rr);
    int best = 0;
    double best_value = 0.0;
    for (int k = -lags; k <= lags; k++) {
        float sum = 0.0f;
        const float *shifted = fr + k;
        for (int i = 0; i < count; i++)
            sum += fl[i] * shifted[i];
        double *score = &self->phase_score[k + MAX_LAG];
        *score += (sum * norm - *score) * PHASE_SMOOTH;
        if (fabs(*score) > fabs(best_value)) {
            best_value = *score;
            best = k;
        }
    }
    if (!self->flipped && best_value < PHASE_FLIP)
        self->flipped = 1;
    else if (self->flipped && best_value > PHASE_UNFLIP)
        self->flipped = 0;
    double at_zero = fabs(self->phase_score[MAX_LAG]);
    int want = 0;
    if (abs(best) >= 2 && fabs(best_value) >= PHASE_MATCH && fabs(best_value) - at_zero > PHASE_GAIN)
        want = best;
    /* keep the current lag while it still matches nearly as well (no flapping) */
    if (self->lag != 0 && want == 0 &&
        fabs(self->phase_score[self->lag + MAX_LAG]) >= PHASE_MATCH - 0.05)
        want = self->lag;
    if (want == self->candidate)
        self->candidate_count++;
    else {
        self->candidate = want;
        self->candidate_count = 1;
    }
    if (self->candidate != self->lag && self->candidate_count >= PHASE_STABLE && self->fade >= 1.0) {
        self->fade_from = self->lag;
        self->lag = self->candidate;
        self->fade = 0.0;
    }
}

/* L/R aligned by lag (+: R is late, L is delayed) */
static void read_aligned(const AutoMaster *self, int lag, double *l, double *r)
{
    int size = 2 * MAX_LAG;
    int dl = lag > 0 ? lag : 0, dr = lag < 0 ? -lag : 0;
    *l = self->input_l[(self->input_head - dl + size) % size];
    *r = self->input_r[(self->input_head - dr + size) % size];
}

static void reset(AutoMaster *self)
{
    int lookahead = (int)(self->rate * LOOKAHEAD_TIME + 0.5);
    if (lookahead < 1)
        lookahead = 1;
    if (lookahead > MAX_LOOKAHEAD)
        lookahead = MAX_LOOKAHEAD;
    self->lookahead = lookahead;
    self->effect.initialDelay = lookahead - 1;
    set_filters(self);
    memset(self->shelf.z1, 0, sizeof(self->shelf.z1));
    memset(self->shelf.z2, 0, sizeof(self->shelf.z2));
    memset(self->highpass.z1, 0, sizeof(self->highpass.z1));
    memset(self->highpass.z2, 0, sizeof(self->highpass.z2));
    self->power_coef = 1.0 - exp(-1.0 / (self->rate * MEASURE_TIME));
    self->power = 0.0;
    self->momentary_coef = 1.0 - exp(-1.0 / (self->rate * GATE_TIME));
    self->momentary = 0.0;
    self->release_coef = 1.0 - exp(-1.0 / (self->rate * RELEASE_TIME));
    self->stereo_coef = 1.0 - exp(-1.0 / (self->rate * STEREO_TIME));
    self->follow_coef = 1.0 - exp(-1.0 / (self->rate * STEREO_FOLLOW));
    self->left_power = self->right_power = self->mid_power = self->side_power = 0.0;
    self->balance_db = self->side_db = 0.0;
    memset(self->bass.z1, 0, sizeof(self->bass.z1));
    memset(self->bass.z2, 0, sizeof(self->bass.z2));
    memset(self->wide_highpass.z1, 0, sizeof(self->wide_highpass.z1));
    memset(self->wide_highpass.z2, 0, sizeof(self->wide_highpass.z2));
    memset(self->wide_delay, 0, sizeof(self->wide_delay));
    for (int band = 0; band < BANDS; band++) {
        for (int k = 0; k < 4; k++) {
            Biquad *b = &self->detect[band][k];
            set_pass(b, self->rate, k < 2 ? BAND_EDGES[band] : BAND_EDGES[band + 1], k < 2);
            memset(b->z1, 0, sizeof(b->z1));
            memset(b->z2, 0, sizeof(b->z2));
        }
        self->detect_mid[band] = self->detect_side[band] = 0.0;
        self->wide_mix[band] = 0.0;
    }
    for (int k = 0; k < 2; k++) {
        set_pass(&self->split_low[k], self->rate, BAND_EDGES[1], 0);
        set_pass(&self->split_rest[k], self->rate, BAND_EDGES[1], 1);
        set_pass(&self->split_mid[k], self->rate, BAND_EDGES[2], 0);
        set_pass(&self->split_high[k], self->rate, BAND_EDGES[2], 1);
        Biquad *all[4] = {&self->split_low[k], &self->split_rest[k], &self->split_mid[k], &self->split_high[k]};
        for (int j = 0; j < 4; j++) {
            memset(all[j]->z1, 0, sizeof(all[j]->z1));
            memset(all[j]->z2, 0, sizeof(all[j]->z2));
        }
    }
    self->wide_head = 0;
    /* velvet noise: one pulse per grid cell, position and sign from a fixed seed,
     * so the sequence is the same on every reopen */
    {
        /* seed 463: flattest 1/3-octave response at 44.1 and 48 kHz of seeds 1..4000 */
        unsigned int seed = 463u;
        int length = (int)(self->rate * VELVET_LENGTH);
        if (length > MAX_WIDE_DELAY - 1)
            length = MAX_WIDE_DELAY - 1;
        int count = (int)(VELVET_LENGTH * VELVET_DENSITY + 0.5);
        if (count > MAX_PULSES)
            count = MAX_PULSES;
        double grid = (double)length / count, energy = 0.0;
        for (int pulse = 0; pulse < count; pulse++) {
            seed = seed * 1103515245u + 12345u;
            double jitter = ((seed >> 8) & 0xffff) / 65536.0;
            seed = seed * 1103515245u + 12345u;
            double sign = (seed >> 16) & 1 ? 1.0 : -1.0;
            int at = (int)(pulse * grid + jitter * (grid - 1.0)) + 1;
            double gain = sign * pow(10.0, VELVET_DECAY / 20.0 * pulse / count);
            self->pulse_at[pulse] = at < MAX_WIDE_DELAY - 1 ? at : MAX_WIDE_DELAY - 1;
            self->pulse_gain[pulse] = (float)gain;
            energy += gain * gain;
        }
        for (int pulse = 0; pulse < count; pulse++)
            self->pulse_gain[pulse] = (float)(self->pulse_gain[pulse] / sqrt(energy));
        self->pulse_count = count;
    }
    self->fast_coef = 1.0 - exp(-1.0 / (self->rate * FAST_TIME));
    self->slow_coef = 1.0 - exp(-1.0 / (self->rate * SLOW_TIME));
    self->duck_coef = 1.0 - exp(-1.0 / (self->rate * DUCK_RELEASE));
    self->fast_env = self->slow_env = 0.0;
    self->duck = 1.0;
    self->fill_power = self->fill_weight = 0.0;
    for (int band = 0; band < BANDS; band++)
        self->fill_band_power[band] = self->fill_band_weight[band] = 0.0;
    set_pass(&self->phase_band[0], self->rate, PHASE_LOW_HZ, 1);
    set_pass(&self->phase_band[1], self->rate, PHASE_HIGH_HZ, 0);
    for (int k = 0; k < 2; k++) {
        memset(self->phase_band[k].z1, 0, sizeof(self->phase_band[k].z1));
        memset(self->phase_band[k].z2, 0, sizeof(self->phase_band[k].z2));
    }
    memset(self->phase_l, 0, sizeof(self->phase_l));
    memset(self->phase_r, 0, sizeof(self->phase_r));
    memset(self->phase_score, 0, sizeof(self->phase_score));
    memset(self->input_l, 0, sizeof(self->input_l));
    memset(self->input_r, 0, sizeof(self->input_r));
    self->phase_head = self->phase_tick = self->input_head = 0;
    self->phase_every = (int)(self->rate * PHASE_EVERY);
    self->max_lag = (int)(self->rate * PHASE_MAX_LAG + 0.5);
    if (self->max_lag > MAX_LAG - 1)
        self->max_lag = MAX_LAG - 1;
    self->flipped = 0;
    self->flip_gain = 1.0;
    self->fade_step = 1.0 / (self->rate * PHASE_FADE);
    self->lag = self->candidate = self->candidate_count = self->fade_from = 0;
    self->fade = 1.0;
    self->fill_coef = 1.0 - exp(-1.0 / (self->rate * FILL_METER_TIME));
    memset(self->delay, 0, sizeof(self->delay));
    memset(self->raw_delay, 0, sizeof(self->raw_delay));
    self->bypass_mix = 0.0;
    for (int index = 0; index < MAX_LOOKAHEAD; index++) {
        self->wanted[index] = 1.0f;
        self->held[index] = 1.0f;
        self->late_gain[index] = 1.0f;
    }
    self->attack = lookahead;
    self->held_sum = lookahead;
    self->head = 0;
    self->release = 1.0;
    self->floor_db = 0.0;
    self->floor_coef = 1.0 - exp(-1.0 / (self->rate * SMOOTH_ATTACK));
    self->floor_step = SMOOTH_RATE / self->rate;
    self->hold_length = (int)(self->rate * SMOOTH_HOLD);
    self->floor_hold = 0;
}

/* ------------------------------------------------------------ audio */

static void process(AEffect *effect, float **inputs, float **outputs, int32_t frames)
{
    AutoMaster *self = (AutoMaster *)effect->object;
    unsigned int mode = _MM_GET_FLUSH_ZERO_MODE();
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_ON);

    int agc = is_on(self->params[P_AGC]);
    int limit = is_on(self->params[P_LIMITER]);
    int balance = is_on(self->params[P_BALANCE]);
    int limit_width = is_on(self->params[P_WIDTH_LIMIT]);
    int bass_mono = is_on(self->params[P_BASS_MONO]);
    double width = get_width(self);
    int mono_wide = is_on(self->params[P_MONO_WIDE]);
    /* target S/M energy per band: Wide Target + band offset, capped at 0 dB (S = M) */
    double wide_target[BANDS];
    for (int band = 0; band < BANDS; band++) {
        double db = get_wide_amount(self) + (band == BANDS - 1 ? get_air(self) : BAND_OFFSET[band]);
        wide_target[band] = pow(10.0, (db < 0.0 ? db : 0.0) / 10.0);
    }

    double target = get_target(self);
    double max_gain = get_max_gain(self);
    double ceiling = pow(10.0, get_ceiling(self) / 20.0);
    double drive = limit ? pow(10.0, get_drive(self) / 20.0) : 1.0;
    int smooth_release = limit && is_on(self->params[P_SMOOTH]);
    double time = get_speed_time(self->params[P_SPEED]);
    /* up at the set speed, down 3x faster */
    double up = 1.0 - exp(-1.0 / (self->rate * time));
    double down = 1.0 - exp(-3.0 / (self->rate * time));
    int lookahead = self->lookahead;
    int attack = (int)(self->rate * get_attack(self) + 0.5);
    if (attack < 1)
        attack = 1;
    if (attack > lookahead)
        attack = lookahead;
    if (attack != self->attack) {
        /* window length changed: recount the sum */
        self->held_sum = 0.0;
        for (int k = 1; k <= attack; k++)
            self->held_sum += self->held[(self->head - k + lookahead) % lookahead];
        self->attack = attack;
    }
    double deepest = 1.0;  /* lowest limiter gain this block */
    int any_sound = 0;

    int phase_fix = is_on(self->params[P_PHASE_FIX]);
    /* A/B: processing and adaptation keep running, so switching back is instant */
    double bypass = (meter_block != NULL && meter_block->bypass) ? 1.0 : 0.0;
    double raw_gain = 1.0;
    for (int32_t n = 0; n < frames; n++) {
        /* phase fix: detect on the raw input; later stages use the corrected signal */
        double in_l = inputs[0][n], in_r = inputs[1][n];
        {
            int head = self->phase_head;
            self->phase_l[head] = (float)run_biquad(&self->phase_band[1], 0, run_biquad(&self->phase_band[0], 0, in_l));
            self->phase_r[head] = (float)run_biquad(&self->phase_band[1], 1, run_biquad(&self->phase_band[0], 1, in_r));
            self->phase_head = (head + 1) % PHASE_WINDOW;
            if (++self->phase_tick >= self->phase_every) {
                self->phase_tick = 0;
                if (phase_fix)
                    estimate_phase(self);
            }
            if (!phase_fix && (self->flipped || self->lag != 0) && self->fade >= 1.0) {
                self->flipped = 0;
                self->fade_from = self->lag;
                self->lag = 0;
                self->fade = 0.0;
                self->candidate = self->candidate_count = 0;
            }
            int size = 2 * MAX_LAG;
            self->input_l[self->input_head] = (float)in_l;
            self->input_r[self->input_head] = (float)in_r;
            double l0, r0;
            read_aligned(self, self->lag, &l0, &r0);
            if (self->fade < 1.0) {
                double l1, r1;
                read_aligned(self, self->fade_from, &l1, &r1);
                l0 = l1 + (l0 - l1) * self->fade;
                r0 = r1 + (r0 - r1) * self->fade;
                self->fade += self->fade_step;
                if (self->fade > 1.0)
                    self->fade = 1.0;
            }
            self->input_head = (self->input_head + 1) % size;
            double want_gain = self->flipped ? -1.0 : 1.0;
            if (self->flip_gain != want_gain) {
                double step = 2.0 * self->fade_step;
                self->flip_gain += self->flip_gain < want_gain ? step : -step;
                if (fabs(self->flip_gain - want_gain) < step)
                    self->flip_gain = want_gain;
            }
            in_l = l0;
            in_r = r0 * self->flip_gain;
        }
        double left = in_l;
        double right = in_r;

        /* AGC: measure before the gain */
        double kl = run_biquad(&self->highpass, 0, run_biquad(&self->shelf, 0, left));
        double kr = run_biquad(&self->highpass, 1, run_biquad(&self->shelf, 1, right));
        double energy = kl * kl + kr * kr;
        self->momentary += (energy - self->momentary) * self->momentary_coef;
        double short_term = -0.691 + 10.0 * log10(self->momentary + 1e-20);
        double long_term = -0.691 + 10.0 * log10(self->power + 1e-20);
        int sounding = short_term > GATE_LUFS;
        double pace = (self->power <= 0.0 || short_term > long_term - RELATIVE_GATE) ?
                      1.0 : RELATIVE_SLOW;
        if (sounding)
            self->power += (energy - self->power) * self->power_coef * pace;
        if (agc) {
            double loudness = -0.691 + 10.0 * log10(self->power + 1e-20);
            if (sounding && loudness > GATE_LUFS) {
                double wanted = target - loudness;
                if (wanted > max_gain)
                    wanted = max_gain;
                if (wanted < MIN_GAIN)
                    wanted = MIN_GAIN;
                self->gain_db += (wanted - self->gain_db) *
                                 (wanted > self->gain_db ? up : down) * pace;
            }
        } else {
            self->gain_db += (0.0 - self->gain_db) * down;
        }
        double gain = pow(10.0, self->gain_db / 20.0);
        raw_gain = gain;  /* A/B dry at the same level, so louder does not sound better */
        left *= gain;
        right *= gain;

        /* stereo: measure the K-weighted input (pre-gain), apply post-gain */
        if (sounding) {
            double mid = (kl + kr) * 0.5, side = (kl - kr) * 0.5;
            double c = self->stereo_coef * pace;
            self->left_power += (kl * kl - self->left_power) * c;
            self->right_power += (kr * kr - self->right_power) * c;
            self->mid_power += (mid * mid - self->mid_power) * c;
            self->side_power += (side * side - self->side_power) * c;
        }
        /* mono detection: band-filter pre-gain M and S */
        double band_mid[BANDS];
        {
            double raw_mid = (in_l + in_r) * 0.5;
            double raw_side = (in_l - in_r) * 0.5;
            for (int band = 0; band < BANDS; band++) {
                double m = raw_mid, s = raw_side;
                for (int k = 0; k < 4; k++) {
                    m = run_biquad(&self->detect[band][k], 0, m);
                    s = run_biquad(&self->detect[band][k], 1, s);
                }
                band_mid[band] = m;
                if (sounding) {
                    double c = self->stereo_coef * pace;
                    self->detect_mid[band] += (m * m - self->detect_mid[band]) * c;
                    self->detect_side[band] += (s * s - self->detect_side[band]) * c;
                }
            }
        }
        double want_balance = 0.0, want_side = 0.0;
        if (self->left_power > 1e-12 && self->right_power > 1e-12) {
            if (balance)
                want_balance = clamp(10.0 * log10(self->left_power / self->right_power),
                                     -BALANCE_LIMIT, BALANCE_LIMIT);
            double ratio = 10.0 * log10((self->side_power + 1e-20) / (self->mid_power + 1e-20));
            if (limit_width && ratio > MONO_SOURCE)
                want_side = clamp(width - ratio, -SIDE_LIMIT, 0.0);
        }
        /* off: back to 0 even in silence; on: holds in silence with measuring */
        {
            double f = self->follow_coef * (sounding ? pace : 1.0);
            if (sounding || !balance)
                self->balance_db += (want_balance - self->balance_db) * f;
            if (sounding || !limit_width)
                self->side_db += (want_side - self->side_db) * f;
        }
        /* mono wide: per band fill only target S energy minus present S */
        int widening = 0;
        for (int band = 0; band < BANDS; band++) {
            double want_mix = 0.0;
            if (mono_wide && self->detect_mid[band] > 1e-14) {
                double have = self->detect_side[band] / self->detect_mid[band];
                want_mix = have < wide_target[band] ? sqrt(wide_target[band] - have) : 0.0;
            }
            if (sounding || !mono_wide)
                self->wide_mix[band] += (want_mix - self->wide_mix[band]) *
                                        self->follow_coef * (sounding ? pace : 1.0);
            widening |= self->wide_mix[band] > 1e-4;
        }
        double mixed[BANDS] = {0.0, 0.0, 0.0};
        if (balance || limit_width || bass_mono || widening ||
            fabs(self->balance_db) > 1e-3 || fabs(self->side_db) > 1e-3) {
            left *= pow(10.0, -self->balance_db / 40.0);
            right *= pow(10.0, self->balance_db / 40.0);
            double mid = (left + right) * 0.5;
            double side = (left - right) * 0.5 * pow(10.0, self->side_db / 20.0);
            /* fake S: M through velvet noise, above 150 Hz only */
            int head = self->wide_head;
            self->wide_delay[head] = (float)mid;
            double made = 0.0;
            for (int pulse = 0; pulse < self->pulse_count; pulse++) {
                int at = head - self->pulse_at[pulse];
                if (at < 0)
                    at += MAX_WIDE_DELAY;
                made += self->pulse_gain[pulse] * self->wide_delay[at];
            }
            self->wide_head = (head + 1) % MAX_WIDE_DELAY;
            made = run_biquad(&self->wide_highpass, 0, made);
            /* transient guard: duck fake S at once when the fast envelope jumps, release slowly;
             * looks above 150 Hz only, or kick-heavy songs stay narrow */
            double level = fabs(run_biquad(&self->wide_highpass, 1, mid));
            self->fast_env += (level - self->fast_env) * self->fast_coef;
            self->slow_env += (level - self->slow_env) * self->slow_coef;
            if (self->fast_env > self->slow_env * TRANSIENT_RATIO + 1e-6)
                self->duck = TRANSIENT_DUCK;
            else
                self->duck += (1.0 - self->duck) * self->duck_coef;
            /* split fake S at 600 Hz and 3 kHz, each band at its own mix; the sum is flat */
            double low = run_biquad(&self->split_low[1], 0, run_biquad(&self->split_low[0], 0, made));
            double rest = run_biquad(&self->split_rest[1], 0, run_biquad(&self->split_rest[0], 0, made));
            double middle = run_biquad(&self->split_mid[1], 0, run_biquad(&self->split_mid[0], 0, rest));
            double high = run_biquad(&self->split_high[1], 0, run_biquad(&self->split_high[0], 0, rest));
            double parts[BANDS] = {low, middle, high};
            for (int band = 0; band < BANDS; band++) {
                mixed[band] = self->wide_mix[band] * self->duck;
                side += parts[band] * mixed[band];
            }
            /* bass mono after adding fake S: also removes low S the 150 Hz highpass leaves */
            if (bass_mono)
                side = run_biquad(&self->bass, 0, side);
            left = mid + side;
            right = mid - side;
        } else {
            /* keep the delay line filled while off, so switching on mixes no silence */
            self->wide_delay[self->wide_head] = (float)((left + right) * 0.5);
            self->wide_head = (self->wide_head + 1) % MAX_WIDE_DELAY;
        }

        /* weighted by band M energy: ducking hits loud moments, so wide_mix
         * or a plain time mean overstates the fill */
        if (sounding || !mono_wide) {
            double added = 0.0, weight = 0.0;
            for (int band = 0; band < BANDS; band++) {
                double w = band_mid[band] * band_mid[band];
                double a = mixed[band] * mixed[band] * w;
                added += a;
                weight += w;
                self->fill_band_power[band] += (a - self->fill_band_power[band]) * self->fill_coef;
                self->fill_band_weight[band] += (w - self->fill_band_weight[band]) * self->fill_coef;
            }
            self->fill_power += (added - self->fill_power) * self->fill_coef;
            self->fill_weight += (weight - self->fill_weight) * self->fill_coef;
        }

        /* limiter: needed gain, window minimum, release, box average */
        left *= drive;
        right *= drive;
        double peak = fabs(left) > fabs(right) ? fabs(left) : fabs(right);
        double need = (limit && peak > ceiling) ? ceiling / peak : 1.0;
        int head = self->head;
        self->wanted[head] = (float)need;
        double minimum = need;
        for (int k = 0; k < attack; k++) {
            float value = self->wanted[(head - k + lookahead) % lookahead];
            if (value < minimum)
                minimum = value;
        }
        if (minimum < self->release)
            self->release = minimum;
        else
            self->release += (minimum - self->release) * self->release_coef;
        double limit_gain = self->release;
        if (smooth_release) {
            double need_db = 20.0 * log10(minimum);
            if (need_db < self->floor_db) {
                self->floor_db += (need_db - self->floor_db) * self->floor_coef;
                self->floor_hold = self->hold_length;
            } else if (self->floor_hold > 0)
                self->floor_hold--;
            else
                self->floor_db = need_db < self->floor_db + self->floor_step ? need_db
                                 : self->floor_db + self->floor_step;
            double floor = pow(10.0, self->floor_db / 20.0);
            if (floor < limit_gain)
                limit_gain = floor;
        } else {
            self->floor_db = 0.0;
        }
        self->held_sum += limit_gain - self->held[(head - attack + lookahead) % lookahead];
        self->held[head] = (float)limit_gain;
        double smooth = self->held_sum / attack;
        if (smooth > 1.0)
            smooth = 1.0;
        if (attack < lookahead) {
            self->late_gain[head] = (float)smooth;
            smooth = self->late_gain[(head - (lookahead - attack) + lookahead) % lookahead];
        }
        if (smooth < deepest)
            deepest = smooth;
        any_sound |= sounding;

        /* delayed by the lookahead; head holds the sample from lookahead - 1 ago */
        int tail = (head + 1) % lookahead;
        float out_left = self->delay[0][tail];
        float out_right = self->delay[1][tail];
        float raw_left = self->raw_delay[0][tail];
        float raw_right = self->raw_delay[1][tail];
        self->delay[0][head] = (float)left;
        self->delay[1][head] = (float)right;
        self->raw_delay[0][head] = (float)(inputs[0][n] * raw_gain);
        self->raw_delay[1][head] = (float)(inputs[1][n] * raw_gain);
        self->head = tail;
        if (lookahead == 1) {
            out_left = (float)left;
            out_right = (float)right;
            raw_left = (float)(inputs[0][n] * raw_gain);
            raw_right = (float)(inputs[1][n] * raw_gain);
        }
        out_left *= (float)smooth;
        out_right *= (float)smooth;
        /* box average rounding can overshoot slightly: clip once more */
        if (limit) {
            if (out_left > ceiling) out_left = (float)ceiling;
            if (out_left < -ceiling) out_left = (float)-ceiling;
            if (out_right > ceiling) out_right = (float)ceiling;
            if (out_right < -ceiling) out_right = (float)-ceiling;
        }
        if (self->bypass_mix != bypass) {
            self->bypass_mix += bypass > self->bypass_mix ? self->fade_step : -self->fade_step;
            if (fabs(self->bypass_mix - bypass) < self->fade_step)
                self->bypass_mix = bypass;
        }
        if (self->bypass_mix > 0.0) {
            double b = self->bypass_mix;
            out_left = (float)(out_left + (raw_left - out_left) * b);
            out_right = (float)(out_right + (raw_right - out_right) * b);
        }
        outputs[0][n] = out_left;
        outputs[1][n] = out_right;
    }
    MeterSlot *slot = self->meter;
    if (slot == NULL && frames > 0)
        slot = self->meter = claim_slot(self);
    if (slot != NULL) {
        slot->agc_db = (float)self->gain_db;
        slot->balance_db = (float)self->balance_db;
        slot->side_db = (float)self->side_db;
        double fill = self->fill_weight > 1e-20 ? self->fill_power / self->fill_weight : 0.0;
        slot->fill_db = fill > 1e-12 ? (float)(10.0 * log10(fill)) : -120.0f;
        slot->limiter_db = (float)(20.0 * log10(deepest > 1e-6 ? deepest : 1e-6));
        slot->loudness = (float)(-0.691 + 10.0 * log10(self->power + 1e-20));
        slot->sounding = any_sound;
        for (int band = 0; band < BANDS; band++) {
            double part = self->fill_band_weight[band] > 1e-20 ?
                          self->fill_band_power[band] / self->fill_band_weight[band] : 0.0;
            slot->fill_band_db[band] = part > 1e-12 ? (float)(10.0 * log10(part)) : -120.0f;
        }
        slot->phase_flip = self->flipped;
        for (int band = 0; band < BANDS; band++) {
            double have = self->detect_mid[band] > 1e-14 ?
                          self->detect_side[band] / self->detect_mid[band] : 0.0;
            slot->band_width_db[band] = have > 1e-12 ? (float)(10.0 * log10(have)) : -120.0f;
            double db = get_wide_amount(self) + (band == BANDS - 1 ? get_air(self) : BAND_OFFSET[band]);
            slot->band_target_db[band] = (float)(db < 0.0 ? db : 0.0);
        }
        slot->phase_delay_ms = (float)(1000.0 * self->lag / self->rate);
        slot->tick = (LONG64)GetTickCount64();
    }
    _MM_SET_FLUSH_ZERO_MODE(mode);
}

/* ------------------------------------------------------------ parameter get/set */

static void set_parameter(AEffect *effect, int32_t index, float value)
{
    AutoMaster *self = (AutoMaster *)effect->object;
    if (index < 0 || index >= PARAM_COUNT)
        return;
    if (value < 0.0f)
        value = 0.0f;
    if (value > 1.0f)
        value = 1.0f;
    if (is_switch(index))
        value = is_on(value) ? 1.0f : 0.0f;
    self->params[index] = value;
}

static float get_parameter(AEffect *effect, int32_t index)
{
    AutoMaster *self = (AutoMaster *)effect->object;
    if (index < 0 || index >= PARAM_COUNT)
        return 0.0f;
    return self->params[index];
}

static void copy_text(void *target, const char *text, size_t size)
{
    if (target == NULL)
        return;
    strncpy((char *)target, text, size - 1);
    ((char *)target)[size - 1] = 0;
}

static void get_display(AutoMaster *self, int32_t index, char *text)
{
    switch (index) {
    case P_AGC:
    case P_BALANCE:
    case P_PHASE_FIX:
    case P_WIDTH_LIMIT:
    case P_BASS_MONO:
    case P_MONO_WIDE:
    case P_LIMITER:
    case P_SMOOTH:
        strcpy(text, is_on(self->params[index]) ? "ON" : "OFF");
        break;
    case P_AIR:
        sprintf(text, "%+.1f", get_air(self));
        break;
    case P_TARGET:
        sprintf(text, "%.1f", get_target(self));
        break;
    case P_MAX_GAIN:
        sprintf(text, "%.1f", get_max_gain(self));
        break;
    case P_SPEED:
        sprintf(text, "%.1f", get_speed_time(self->params[P_SPEED]));
        break;
    case P_WIDTH:
        sprintf(text, "%.1f", get_width(self));
        break;
    case P_WIDE_AMOUNT:
        sprintf(text, "%.1f", get_wide_amount(self));
        break;
    case P_CEILING:
        sprintf(text, "%.1f", get_ceiling(self));
        break;
    case P_DRIVE:
        sprintf(text, "%+.1f", get_drive(self));
        break;
    case P_ATTACK:
        sprintf(text, "%.2f", get_attack(self) * 1000.0);
        break;
    default:
        text[0] = 0;
    }
}

static intptr_t dispatch(AEffect *effect, int32_t opcode, int32_t index, intptr_t value,
                         void *pointer, float option)
{
    AutoMaster *self = (AutoMaster *)effect->object;
    char text[64];
    (void)value;
    (void)option;
    switch (opcode) {
    case EFF_OPEN:
        return 0;
    case EFF_CLOSE:
        if (self->meter != NULL) {
            self->meter->tick = 0;
            InterlockedExchange64(&self->meter->owner, 0);
        }
        free(self);
        return 1;
    case EFF_GET_PROGRAM:
        return 0;
    case EFF_GET_PROGRAM_NAME:
        copy_text(pointer, "Default", 24);
        return 1;
    case EFF_GET_PARAM_LABEL:
        if (index >= 0 && index < PARAM_COUNT)
            copy_text(pointer, PARAM_LABELS[index], 8);
        return 0;
    case EFF_GET_PARAM_DISPLAY:
        if (index >= 0 && index < PARAM_COUNT) {
            get_display(self, index, text);
            copy_text(pointer, text, 8);
        }
        return 0;
    case EFF_GET_PARAM_NAME:
        if (index >= 0 && index < PARAM_COUNT)
            copy_text(pointer, PARAM_NAMES[index], 32);
        return 0;
    case EFF_SET_SAMPLE_RATE:
        if (option > 0.0f) {
            self->rate = option;
            reset(self);
        }
        return 0;
    case EFF_SET_BLOCK_SIZE:
        return 0;
    case EFF_MAINS_CHANGED:
        if (value)
            reset(self);
        return 0;
    case EFF_GET_PARAMETER_PROPERTIES:
        if (index >= 0 && index < PARAM_COUNT && pointer != NULL) {
            ParameterProperties *props = (ParameterProperties *)pointer;
            int16_t category = PARAM_CATEGORIES[index];
            int16_t count = 0;
            memset(props, 0, sizeof(*props));
            for (int other = 0; other < PARAM_COUNT; other++)
                count += PARAM_CATEGORIES[other] == category;
            copy_text(props->label, PARAM_NAMES[index], sizeof(props->label));
            props->flags = PARAM_SUPPORTS_DISPLAY_CATEGORY;
            if (is_switch(index))
                props->flags |= PARAM_IS_SWITCH;
            props->category = category;
            props->numParametersInCategory = count;
            copy_text(props->categoryLabel, CATEGORY_LABELS[category], sizeof(props->categoryLabel));
            return 1;
        }
        return 0;
    case EFF_GET_PLUG_CATEGORY:
        return CATEGORY_MASTERING;
    case EFF_GET_EFFECT_NAME:
        copy_text(pointer, "PyWinAudio Auto Master", 32);
        return 1;
    case EFF_GET_PRODUCT_STRING:
        copy_text(pointer, "PyWinAudio Auto Master", 64);
        return 1;
    case EFF_GET_VENDOR_STRING:
        copy_text(pointer, "PyWinAudio", 64);
        return 1;
    case EFF_GET_VENDOR_VERSION:
        return VERSION;
    case EFF_CAN_DO:
        return 0;
    case EFF_GET_VST_VERSION:
        return 2400;
    }
    return 0;
}

/* ------------------------------------------------------------ entry point */

__declspec(dllexport) AEffect *VSTPluginMain(AudioMaster master)
{
    if (master == NULL || master(NULL, MASTER_VERSION, 0, 0, NULL, 0.0f) == 0)
        return NULL;
    AutoMaster *self = (AutoMaster *)calloc(1, sizeof(AutoMaster));
    if (self == NULL)
        return NULL;
    self->master = master;
    for (int index = 0; index < PARAM_COUNT; index++)
        self->params[index] = PARAM_DEFAULTS[index];
    self->rate = 48000.0;
    AEffect *effect = &self->effect;
    effect->magic = MAGIC;
    effect->dispatcher = dispatch;
    effect->process = process;
    effect->setParameter = set_parameter;
    effect->getParameter = get_parameter;
    effect->numPrograms = 1;
    effect->numParams = PARAM_COUNT;
    effect->numInputs = 2;
    effect->numOutputs = 2;
    effect->flags = FLAG_CAN_REPLACING;
    effect->ioRatio = 1.0f;
    effect->object = self;
    effect->uniqueID = UNIQUE_ID;
    effect->version = VERSION;
    effect->processReplacing = process;
    reset(self);
    return effect;
}
