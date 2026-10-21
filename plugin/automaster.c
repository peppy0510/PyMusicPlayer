/*
 * author: Taehong Kim
 * email: peppy0510@hotmail.com
 *
 * Copied from PyWinAudio (plugin/automaster.c at 38b1f61) for PyMusicPlayer's LOUD, the
 * shared memory's name (METER_NAME) its only change: keep it the same as PyWinAudio's otherwise.
 *
 * PyWinAudio Auto Master — 방송 프로세서처럼 소리를 곡마다 손대지 않고 고르게 다듬는 VST2 플러그인.
 * 자동 레벨(AGC), 스테레오 보정, 미리 보는 피크 리미터. 레벨만 맞추는 것이 아니라 Leveler 에서
 * 이름을 바꿨다(사용자). Equalizer APO 가 audiodg 안에서 올려
 * 실시간으로 돌린다. 화면은 없고, 랙이 파라미터를 손잡이·단추로 보여 준다.
 *
 * VST2 의 바깥 모양(AEffect 구조체와 함수 포인터 넷, 디스패처 번호)은 source/vsthost.py
 * 와 같은 배치를 여기에 직접 적는다. Steinberg SDK 는 쓰지 않는다.
 *
 * AGC: 들어오는 소리를 BS.1770 K 가중으로 재고(약 3 초 평균) 목표 라우드니스까지 이득을
 * 천천히 움직인다. 재는 것은 이득을 걸기 전 소리라 제 출력을 쫓는 되먹임이 없다. 조용하면
 * (0.05 초 라우드니스가 -45 LUFS 아래) 재는 값도 이득도 그대로 둔다. 긴 평균보다 10 dB 넘게
 * 낮은 쉼·페이드에서는 열 배 느리게 따라간다 — 곡 사이 무음에서
 * 이득이 치솟지 않고, 소리가 돌아왔을 때 무음 동안 줄어든 평균 때문에 튀지도 않게.
 *
 * 리미터: 5 ms 앞을 내다보고 줄인다. 앞으로 올 피크까지 필요한 이득의 최솟값을 창으로 잡고,
 * 같은 길이의 상자 평균으로 매끈하게 내려가 피크가 올 때 정확히 그 값에 닿는다. 풀릴 때는
 * 따로 천천히. 소리는 그만큼 늦게 나가고, 그 늦음을 initialDelay 로 알린다.
 * Drive 는 리미터 앞에서 미는 이득(0~+30 dB) — 헤드룸을 끝까지 채운다(LoudMax 의 Threshold 자리, 사용자).
 * Smooth 는 두 번째 풀림: 줄인 양의 바닥을 0.3 초로 따라가고, 마지막으로 깊어진 뒤 0.15 초를
 * 기다렸다가 초당 10 dB 로만 오른다. 빠른 풀림은 그 바닥 위로 못 올라가 꽉 민 소리의 출렁임이
 * 줄고(±0.50 → 0.30 dB, LoudMax 0.26), 큰 구간 뒤에는 2 초쯤에 걸쳐 돌아온다(LoudMax 출력 곡선
 * 실측: 0.2 초 2.4 dB, 1 초 9.7 dB, 2 초 17.6 dB). 기다림을 늘리면 출렁임은 더 줄지만 그만큼 덜 차고
 * 늦게 돌아온다(0.25 초: 0.26 dB, −0.3 dB 더 작음).
 * Attack 은 줄이기 시작하는 길이(0.5~5 ms). 늦음은 늘 5 ms 그대로 두고 이득만 그 차이만큼 늦춰
 * 짧은 비탈도 피크에 정확히 닿는다. 5 ms 는 타격음 4 ms 앞부터 주변 소리까지 눌러 뭉개 들리고,
 * LoudMax 는 0.5 ms 앞부터만 줄인다(실측, 사용자 "LoudMax 가 더 깔끔한 느낌").
 *
 * 스테레오 보정(AGC 와 리미터 사이): 들어오는 소리를 약 5 초 평균으로 재서
 *   좌우 균형 — 한쪽이 늘 크면 양쪽에 반씩 나눠 맞춘다(최대 ±3 dB씩).
 *   폭 상한 — 옆(S)이 가운데(M) 대비 상한(Max Width)보다 크면(지나치게 넓거나 위상이 어긋난
 *     소리) 그만큼 S 를 줄인다(최대 6 dB). 넓히지는 않는다 — 넓히기는 모노 넓히기가 모자란
 *     만큼만 맡고, 괜찮은 스테레오는 그대로 나간다(사용자).
 *   저역 모노 — 120 Hz 아래의 S 를 걷어 낮은 소리를 가운데로 모은다.
 *   모노 넓히기 — 거의 모노면 M 을 벨벳 노이즈(듬성한 무작위 ±1 펄스열, 25 ms, 초당 1500 개,
 *     뒤로 갈수록 작아지게)에 통과시켜 가짜 S 를 만들고 L 에 더하고 R 에서 뺀다(Alary·Politis·
 *     Välimäki DAFx-17 의 벨벳 노이즈 비상관기). 몇 갈래 지연을 더하던 것보다 빗살 색이 덜
 *     묻고 넓게 퍼진다. L+R 은 원래 소리 그대로라 모노로 들어도 빗살이 생기지 않는다. 150 Hz
 *     아래는 만들지 않아 킥·서브 베이스는 가운데에 남는다. 타격음(빠른 포락이 느린 포락보다
 *     6 dB 넘게 높을 때)에서는 가짜 S 를 잠깐 줄여 어택이 번지지 않게 한다(DAFx-24 StereoWidener
 *     의 트랜지언트 처리와 같은 생각).
 *     150 Hz 위를 150–600 Hz·600 Hz–3 kHz·3 kHz 위 세 대역으로 나눠(Linkwitz-Riley 4 차) 대역마다
 *     S/M 을 재고 따로 채운다(Ozone Imager 처럼 — 사용자). 목표는 Wide Target 에 중저역 -5 dB,
 *     중역 0, 고역은 Air 손잡이(-6~+6 dB, 처음 +2). 판정 위 끝은 10 kHz — 전 대역 한 덩어리로 재면 MP3 가 고역에 남긴
 *     S(-20 dB 안팎) 때문에 거의 모노인 곡도 반쯤 스테레오로 읽혔다.
 *     가짜 S 는 모자란 만큼만 채운다: 목표 넓이(Wide Target)의 S 에너지에서 지금 있는 S 를
 *     뺀 나머지. 이미 목표만큼 넓은 소리에는 아무것도 더하지 않아 그대로 나가고, 모노는 목표
 *     까지, 좁은 소리는 모자란 만큼만 넓어진다 — 방송 중에 곡마다 맞출 수 없으니(사용자).
 * 무음에서는 AGC 처럼 재기를 멈춘다.
 *
 * 계기: 단계마다 지금 얼마나 고치고 있는지(AGC 이득, 좌우 보정, 폭 줄임, 모노 채움, 리미터
 * 줄임)를 블록마다 공유 메모리 "Global\PyWinAudioAutoMaster" 에 적는다. 플러그인은 audiodg(세션 0,
 * LocalService) 안에 있고 랙은 사용자 세션에 있어 Global 이름과 모두 읽을 수 있는 DACL 을 쓴다.
 * 인스턴스마다 칸 하나를 잡고, 랙은 가장 최근에 소리를 처리한 칸을 읽는다.
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

/* VST2 의 VstParameterProperties. 호스트가 묶음(구역)과 켜고 끄는 값을 알 수 있다. */
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

/* ------------------------------------------------------------ 파라미터 */

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
/* 구역: 1 AGC, 2 Stereo, 3 Limiter. 랙이 구역 사이에 금을 긋는다.
 * 예전 Stereo 하나가 좌우 균형과 폭 상한을 함께 켜고 꺼서, 스테레오 처리가 다 꺼지는 것처럼 읽혔다 —
 * Balance·Width Limit 둘로 나눴다(사용자). 랙은 저장된 Stereo 값을 둘에 옮긴다. */
static const int16_t PARAM_CATEGORIES[PARAM_COUNT] = {1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3};
static const char *CATEGORY_LABELS[4] = {"", "AGC", "Stereo", "Limiter"};
static const char *PARAM_LABELS[PARAM_COUNT] = {
    "", "LUFS", "dB", "s", "", "", "", "S/M dB", "", "", "S/M dB", "dB", "", "dB", "dB", "", "ms"
};
/* 처음 값: AGC 켬, -16 LUFS, 최대 +9 dB, 약 3 초, 좌우 균형 켬, 폭 상한 켬(S/M -6 dB), 저역 모노 켬,
 * 모노 넓히기 켬, 목표 넓이 S/M -7.5 dB(보통 스테레오 곡의 가운데 대역은 이보다 넓어 손대지 않는다 —
 * 실측 진짜 스테레오 -6.5 보다 조금 좁게, 사용자), 고역 몫(Air) +2 dB(3 대역 전과 같은 소리),
 * 위상 바로잡기 켬, 리미터 켬, -1 dBFS. Drive 0 dB·Smooth 끔 — 넣기 전과 같은 소리. Attack 은 1 ms
 * (0.5~5 ms 를 재어 본 가운데 앞 눌림·출렁임이 가장 적고 잡음은 LoudMax 보다 적다, 사용자). */
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
/* 짧은 라우드니스가 긴 평균보다 이만큼 낮으면(곡 사이 쉼·페이드) 재는 것도 이득도 열 배
 * 느리게 따라간다. 아주 멈추면 크게 조용해진 곡에 끝내 맞추지 못한다. */
#define RELATIVE_GATE 10.0
#define RELATIVE_SLOW 0.1
#define STEREO_TIME 5.0
#define STEREO_FOLLOW 2.0
#define BALANCE_LIMIT 6.0      /* 좌우 차이를 이만큼까지 고친다(한쪽에 반씩, ±3 dB) */
#define SIDE_LIMIT 6.0
#define WIDTH_LOW -18.0
#define WIDTH_HIGH -4.0
#define MONO_SOURCE -30.0      /* S 가 M 보다 이만큼 낮으면 모노 소스 */
#define BASS_MONO_HZ 120.0
#define WIDE_LOW -18.0
#define WIDE_HIGH 0.0
/* 모노 넓히기는 150 Hz 위를 세 대역으로 나눠 따로 재고 따로 채운다(Ozone Imager 처럼 — 사용자).
 * 목표는 Wide Target 에 대역마다 더하는 값: 중저역은 적게(뭉개지고 위상감이 나기 쉽다), 고역은
 * Air 로(공기감 — 진짜 스테레오 곡의 고역까지 넓히면 귀로 낮출 수 있게 손잡이로 뺐다, 사용자). 판정 맨 위는 10 kHz 에서 끊는다 — MP3 가 잘라 낸 위쪽은 재지 않는다. */
#define BANDS 3
static const double BAND_EDGES[BANDS + 1] = {150.0, 600.0, 3000.0, 10000.0};
/* 고역 몫은 Air 손잡이가 정한다(여기 마지막 칸은 쓰지 않는다). */
static const double BAND_OFFSET[BANDS] = {-5.0, 0.0, 0.0};
#define AIR_LOW -6.0
#define AIR_HIGH 6.0
#define WIDE_HZ 150.0
#define MAX_WIDE_DELAY 8192    /* 192 kHz 에서 42 ms — 가장 긴 갈래 27 ms 를 넉넉히 담는다 */
#define VELVET_LENGTH 0.025      /* 초 */
#define VELVET_DENSITY 1500.0    /* 초당 펄스 */
#define VELVET_DECAY -30.0       /* 끝 펄스의 크기(dB) */
#define MAX_PULSES 64
#define TRANSIENT_RATIO 3.0      /* 빠른/느린 포락 비(9.5 dB) 넘으면 타격음 */
#define TRANSIENT_DUCK 0.4       /* 타격음 동안 가짜 S 를 이만큼으로(킥이 많은 곡도 평균 넓이를 크게 잃지 않게) */
#define FAST_TIME 0.001
#define SLOW_TIME 0.05
#define DUCK_RELEASE 0.03
/* 모노 채움 계기의 평균 시간. 타격음 지킴이 줄인 것까지 넣어 실제로 섞인 양(띠 에너지 가중)을 보인다. */
#define FILL_METER_TIME 1.0
/* 위상 바로잡기(Phase Fix): 입력 L·R 의 150 Hz–4 kHz 를 ±2 ms 상호상관으로 0.25 초마다 재고(약 1 초로
 * 고르게), 가장 센 상관이 -0.5 아래면 R 의 극성을 뒤집고(-0.2 위로 오면 되돌림), 0 이 아닌 어긋남에서
 * 상관이 0.85 이상이면서 어긋남 0 보다 0.08 넘게 높고 세 번 이어지면 앞선 쪽을 그만큼 늦춘다. 일부러
 * 벌린 마이크의 진짜 스테레오는 두 채널이 그만큼 닮지 않아 건드리지 않는다. 바꿀 때는 20 ms 에 걸쳐. */
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
#define SMOOTH_ATTACK 0.3      /* 초: 바닥이 깊어질 때 */
#define SMOOTH_RATE 10.0       /* dB/초: 바닥이 풀릴 때 */
#define ATTACK_LOW 0.0005
#define SMOOTH_HOLD 0.15       /* 초: 마지막으로 깊어진 뒤 이만큼 기다렸다 풀린다 */

/* ------------------------------------------------------------ 계기(공유 메모리) */

#define METER_MAGIC 0x4D415750 /* 'PWAM' */
/* 칸 배치가 바뀌면 이름도 바꾼다 — 옛 DLL 이 아직 도는 엔진이 같은 이름에 짧은 칸으로 만들어 둔
 * 공유 메모리에 새 배치로 쓰면 넘친다. */
#define METER_VERSION 4
/* PyMusicPlayer: its own name, so it neither shows on the PyWinAudio rack's meters nor
 * follows the rack's A/B bypass */
#define METER_NAME L"PyMusicPlayerAutoMaster.v4"
#define METER_SLOTS 8

typedef struct {
    volatile LONG64 owner;  /* 칸을 쥔 인스턴스(포인터 값). 0 이면 빈 칸 */
    volatile LONG64 tick;   /* 마지막으로 소리를 처리한 GetTickCount64 */
    float agc_db;           /* 지금 거는 AGC 이득 */
    float balance_db;       /* 좌우 보정(+ 면 왼쪽을 내림) */
    float side_db;          /* 폭 줄임(0 이하) */
    float fill_db;          /* 실제로 섞인 가짜 S 크기(M 대비 dB, 1 초 평균, 없으면 -120) */
    float limiter_db;       /* 이 블록에서 리미터가 가장 깊게 줄인 값(0 이하) */
    float loudness;         /* 재고 있는 입력 라우드니스(LUFS) */
    int32_t sounding;
    int32_t phase_flip;     /* R 극성을 뒤집고 있으면 1 */
    float fill_band_db[3];  /* 대역마다 섞인 가짜 S(150–600 Hz·600 Hz–3 kHz·3 kHz 위) */
    float phase_delay_ms;   /* 맞추느라 늦추고 있는 시간(+ 면 L 을, - 면 R 을) */
    float band_width_db[3]; /* 대역마다 들어온 소리의 넓이(S/M dB, 판정에 쓰는 평균) */
    float band_target_db[3];/* 대역마다 목표 넓이(Wide Target + 대역 몫) */
} MeterSlot;

typedef struct {
    uint32_t magic;
    uint32_t version;
    /* 랙이 쓰는 칸: 0 이 아니면 A/B 비교 중 — 원래 소리를 같은 크기·같은 늦음으로 내보낸다. 설정 줄을
     * 바꾸면 엔진이 플러그인을 새로 만들어 적응이 처음부터 다시 쌓이므로, 비교는 여기로만 오간다. */
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
    /* 누구나 읽고 쓰기(랙은 읽기만 한다). */
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
        /* 비었거나 10 초 넘게 아무도 안 쓴(죽은 프로세스가 남긴) 칸을 차지한다. */
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

/* ------------------------------------------------------------ 상태 */

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
    double power;          /* K 가중 평균 제곱(두 채널 합) */
    double power_coef;
    double momentary;      /* 0.05 초 평균 제곱 — 무음·쉼 판정용 */
    double momentary_coef;
    double gain_db;        /* 지금 걸고 있는 AGC 이득 */

    double left_power, right_power, mid_power, side_power;
    double stereo_coef, follow_coef;
    double balance_db;     /* 왼쪽이 크면 + — 왼쪽을 반만큼 내리고 오른쪽을 반만큼 올린다 */
    double side_db;        /* S 에 걸고 있는 이득 */
    Biquad bass;           /* S 의 120 Hz 고역 통과 */
    Biquad wide_highpass;  /* 가짜 S 의 150 Hz 고역 통과 */
    /* 모노 판정: 대역마다 아래 끝 고역 통과 둘·위 끝 저역 통과 둘(Linkwitz-Riley 4 차, 0 = M, 1 = S) */
    Biquad detect[BANDS][4];
    double detect_mid[BANDS], detect_side[BANDS];
    /* 가짜 S 를 세 대역으로 나누는 크로스오버(600 Hz·3 kHz, 각 LR4 = 2 차 둘) */
    Biquad split_low[2], split_rest[2], split_mid[2], split_high[2];
    float wide_delay[MAX_WIDE_DELAY];
    int wide_head;
    int pulse_count;
    int pulse_at[MAX_PULSES];      /* 펄스 자리(표본) */
    float pulse_gain[MAX_PULSES];  /* 부호 × 크기, 제곱합 1 */
    double fast_env, slow_env, duck;
    double fast_coef, slow_coef, duck_coef;
    double wide_mix[BANDS];  /* 대역마다 지금 섞고 있는 가짜 S 의 크기(M 대비 배율) */
    /* 계기용: 실제로 섞인 가짜 S 배율(wide_mix × duck)의 제곱을 띠 M 에너지로 가중한 평균의 분자·분모 */
    double fill_power, fill_weight;
    double fill_band_power[BANDS], fill_band_weight[BANDS];
    double fill_coef;

    /* 위상 바로잡기 */
    Biquad phase_band[2];        /* 판정용 150 Hz 고역·4 kHz 저역 통과(0 = L, 1 = R) */
    float phase_l[PHASE_WINDOW], phase_r[PHASE_WINDOW];
    float flat_l[PHASE_WINDOW], flat_r[PHASE_WINDOW];  /* 잴 때 창을 일자로 펴 둔 것(나머지 셈 없이) */
    int phase_head, phase_tick, phase_every, max_lag;
    double phase_score[2 * MAX_LAG + 1];
    int flipped;
    double flip_gain, fade_step;
    int lag, candidate, candidate_count;  /* 지금 맞추고 있는 어긋남, 다음 후보와 이어진 횟수 */
    int fade_from;                        /* 바꾸는 중이면 이전 어긋남 */
    double fade;                          /* 0 → 1 */
    float input_l[2 * MAX_LAG], input_r[2 * MAX_LAG];
    int input_head;

    int lookahead;         /* 리미터가 내다보는 표본 수 */
    float delay[2][MAX_LOOKAHEAD];
    float raw_delay[2][MAX_LOOKAHEAD];  /* A/B 의 원래 소리(AGC 이득만 곱해 크기를 맞춘 것) */
    double bypass_mix;                  /* 0 = 처리한 소리, 1 = 원래 소리 */
    float wanted[MAX_LOOKAHEAD];  /* 표본마다 필요한 이득 */
    float held[MAX_LOOKAHEAD];    /* 창 최솟값(풀림 적용 뒤) */
    int head;
    double held_sum;
    double release;        /* 지금 풀리고 있는 이득 */
    double floor_db;       /* Smooth 의 바닥(dB, 0 이하) */
    double floor_coef, floor_step;
    int floor_hold, hold_length;
    int attack;                   /* 비탈 길이(표본), lookahead 이하 */
    float late_gain[MAX_LOOKAHEAD];  /* 비탈이 짧으면 이득을 lookahead - attack 만큼 늦춘다 */
    MeterSlot *meter;      /* 계기 칸(없으면 NULL) */
    double release_coef;
} AutoMaster;

static double get_speed_time(float value)
{
    /* 0 → 10 초(느림), 1 → 1 초(빠름). 가운데가 약 3 초. */
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

/* BS.1770 K 가중의 두 단(높은 선반 + RLB 고역 통과). 표본 빠르기마다 계수를 다시 낸다. */
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

    /* 저역 모노용 2 차 버터워스 고역 통과(S 에만). */
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

/* 판정 창의 ±max_lag 상호상관을 재서 고르게 하고, 극성 뒤집기와 맞출 어긋남을 정한다. */
static void estimate_phase(AutoMaster *self)
{
    int lags = self->max_lag;
    int count = PHASE_WINDOW - 2 * lags;
    int start = self->phase_head;  /* 가장 오래된 표본 */
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
        return;  /* 조용하면 재지 않는다 */
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
    /* 맞추고 있는 어긋남이 아직 거의 그만큼 닮았으면 그대로 둔다(흔들리지 않게). */
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

/* 어긋남 lag(+ 면 R 이 늦다 → L 을 늦춘다)만큼 맞춘 L·R. */
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
    /* 벨벳 노이즈: 고른 칸마다 펄스 하나, 칸 안 자리와 부호는 정해진 씨앗의 난수. 매번 같은 열이
     * 나와 다시 열어도 소리가 바뀌지 않는다. */
    {
        /* 씨앗 463: 1~4000 가운데 44.1·48 kHz 모두 1/3 옥타브 응답이 가장 고른 열(편차 0.6 dB). */
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

/* ------------------------------------------------------------ 소리 */

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
    /* 대역마다 목표 S/M 에너지 비 — Wide Target 에 대역 몫을 더하되 0 dB(S = M) 를 넘지 않게. */
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
    /* 올릴 때는 정한 빠르기, 내릴 때는 세 배 빠르게 — 갑자기 커지는 소리를 오래 두지 않는다. */
    double up = 1.0 - exp(-1.0 / (self->rate * time));
    double down = 1.0 - exp(-3.0 / (self->rate * time));
    int lookahead = self->lookahead;
    int attack = (int)(self->rate * get_attack(self) + 0.5);
    if (attack < 1)
        attack = 1;
    if (attack > lookahead)
        attack = lookahead;
    if (attack != self->attack) {
        /* 창 길이가 바뀌면 합을 새 창으로 다시 센다 */
        self->held_sum = 0.0;
        for (int k = 1; k <= attack; k++)
            self->held_sum += self->held[(self->head - k + lookahead) % lookahead];
        self->attack = attack;
    }
    double deepest = 1.0;  /* 이 블록에서 리미터가 건 가장 작은 이득 */
    int any_sound = 0;

    int phase_fix = is_on(self->params[P_PHASE_FIX]);
    /* A/B: 비교 중이어도 처리와 적응은 그대로 돌린다 — 되돌리는 순간 바로 처리한 소리가 나온다. */
    double bypass = (meter_block != NULL && meter_block->bypass) ? 1.0 : 0.0;
    double raw_gain = 1.0;
    for (int32_t n = 0; n < frames; n++) {
        /* 위상 바로잡기: 판정은 들어온 그대로의 소리로, 바로잡은 소리는 그 뒤 모든 단계가 쓴다. */
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

        /* AGC: 이득 걸기 전 소리를 잰다. */
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
        raw_gain = gain;  /* A/B 의 원래 소리도 같은 크기로 — 큰 쪽이 좋게 들리지 않게 */
        left *= gain;
        right *= gain;

        /* 스테레오 보정: 재는 것은 K 가중 입력(이득 앞), 거는 것은 이득 뒤 소리. */
        if (sounding) {
            double mid = (kl + kr) * 0.5, side = (kl - kr) * 0.5;
            double c = self->stereo_coef * pace;
            self->left_power += (kl * kl - self->left_power) * c;
            self->right_power += (kr * kr - self->right_power) * c;
            self->mid_power += (mid * mid - self->mid_power) * c;
            self->side_power += (side * side - self->side_power) * c;
        }
        /* 모노 판정: 이득 앞 입력의 M·S 를 대역마다 거른다. */
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
        /* 끄면 소리가 없어도 0 으로 돌아간다. 켜져 있을 때 무음이면 재기와 함께 멈춘다. */
        {
            double f = self->follow_coef * (sounding ? pace : 1.0);
            if (sounding || !balance)
                self->balance_db += (want_balance - self->balance_db) * f;
            if (sounding || !limit_width)
                self->side_db += (want_side - self->side_db) * f;
        }
        /* 모노 넓히기: 대역마다 목표 S 에너지에서 지금 있는 S 를 뺀 만큼만 가짜 S 로 채운다. */
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
            /* 가짜 S: M 을 벨벳 노이즈에 통과시킨 것, 150 Hz 위만. */
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
            /* 타격음 지킴: 빠른 포락이 느린 포락을 크게 넘으면 가짜 S 를 곧바로 줄였다 천천히 푼다.
             * 가짜 S 가 있는 150 Hz 위만 본다 — 킥의 낮은 쿵까지 보면 킥이 많은 곡은 늘 좁아졌다. */
            double level = fabs(run_biquad(&self->wide_highpass, 1, mid));
            self->fast_env += (level - self->fast_env) * self->fast_coef;
            self->slow_env += (level - self->slow_env) * self->slow_coef;
            if (self->fast_env > self->slow_env * TRANSIENT_RATIO + 1e-6)
                self->duck = TRANSIENT_DUCK;
            else
                self->duck += (1.0 - self->duck) * self->duck_coef;
            /* 가짜 S 를 600 Hz·3 kHz 에서 셋으로 나눠 대역마다 제 배율로. 셋을 더하면 크기는 평평하다. */
            double low = run_biquad(&self->split_low[1], 0, run_biquad(&self->split_low[0], 0, made));
            double rest = run_biquad(&self->split_rest[1], 0, run_biquad(&self->split_rest[0], 0, made));
            double middle = run_biquad(&self->split_mid[1], 0, run_biquad(&self->split_mid[0], 0, rest));
            double high = run_biquad(&self->split_high[1], 0, run_biquad(&self->split_high[0], 0, rest));
            double parts[BANDS] = {low, middle, high};
            for (int band = 0; band < BANDS; band++) {
                mixed[band] = self->wide_mix[band] * self->duck;
                side += parts[band] * mixed[band];
            }
            /* 저역 모노는 가짜 S 까지 더한 뒤에 — 150 Hz 고역 통과가 다 못 거른 낮은 S 도 걷는다. */
            if (bass_mono)
                side = run_biquad(&self->bass, 0, side);
            left = mid + side;
            right = mid - side;
        } else {
            /* 꺼져 있어도 지연선은 채워 둔다 — 켜는 순간 빈 소리가 섞이지 않게. */
            self->wide_delay[self->wide_head] = (float)((left + right) * 0.5);
            self->wide_head = (self->wide_head + 1) % MAX_WIDE_DELAY;
        }

        /* 계기는 wide_mix 만 보면 타격음 지킴이 줄인 만큼을 놓쳐 드럼 많은 곡에서 5 dB 크게 보였다.
         * 지킴은 소리가 큰 순간에 걸리므로 시간 평균으로는 안 드러난다 — 띠 M 에너지로 가중한다. */
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

        /* 리미터: 이 표본에 필요한 이득, 창 최솟값, 풀림, 상자 평균. */
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

        /* 내다본 만큼 늦게 내보낸다. head 자리에는 lookahead - 1 표본 전 소리가 있다. */
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
        /* 상자 평균의 반올림 때문에 아주 조금 넘을 수 있다. 끝에서 한 번 더 막는다. */
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

/* ------------------------------------------------------------ 파라미터 읽고 쓰기 */

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

/* ------------------------------------------------------------ 들머리 */

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
