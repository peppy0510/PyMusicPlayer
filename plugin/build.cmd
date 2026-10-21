@echo off
rem ASCII only: cmd misreads UTF-8 lines on code page 949 PCs.
rem Builds the Auto Master copied from PyWinAudio (automaster.c) as a 64-bit VST2 DLL for LOUD,
rem with the Visual Studio 2022 C compiler, into assets\dlls.
setlocal
set HERE=%~dp0
for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS=%%i
if not defined VS (echo [ ERROR ] Visual Studio 2022 C++ build tools not found & exit /b 1)
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist "%HERE%build" mkdir "%HERE%build"
cl /nologo /O2 /fp:fast /MT /W3 /D_CRT_SECURE_NO_WARNINGS /D_USE_MATH_DEFINES /LD "%HERE%automaster.c" /Fo"%HERE%build\\" /Fe"%HERE%build\PyMusicPlayerAutoMaster.dll" advapi32.lib /link /DEF:"%HERE%automaster.def" || exit /b 1
copy /y "%HERE%build\PyMusicPlayerAutoMaster.dll" "%HERE%..\assets\dlls\" >nul || exit /b 1
echo [ BUILT ] assets\dlls\PyMusicPlayerAutoMaster.dll
