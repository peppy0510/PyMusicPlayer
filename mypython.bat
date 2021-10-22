set PYTHON_HOME=%~dp0
set PYTHON_NAME=%1.exe
copy "%PYTHON_HOME%python.exe" "%PYTHON_HOME%%PYTHON_NAME%"
set args=%*
set args=%args:* =%
"%PYTHON_HOME%%PYTHON_NAME%" %args%
