# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import os
import shutil
import subprocess
# import re
# import sys
# import psutil


BUILD_MFEATS = False


# PIL License: Python (MIT style)
# SciPy is a set of open source (BSD licensed)
# Numpy is licensed under the BSD license, enabling reuse with few restrictions.
# mean # fft.fft # zeros # log2 # kaiser # ceil # interp # floor # sum # max
# linspace # arange # mean # arange # abs # concatenate # int8 # int16 # int32
# array # delete # hamming # interp # round # convolve # pi # sin # cos # power


def main():

    remove_paths = [r'build', r'dist\macrobox', r'dist\mfeats']
    for path in remove_paths:
        path = os.path.abspath(path)
        print('removing %s' % (path))
        try:
            shutil.rmtree(path)
        except:
            pass

    builder_path = r'''C:\Program Files (x86)\Python27\Lib'''
    builder_path += r'''\site-packages\pyinstaller\pyinstaller.py'''
    commands = ['python -O "%s" "macrobox.spec"' % (builder_path)]
    if BUILD_MFEATS:
        commands += ['python -O "%s" "mfeats.spec"' % (builder_path)]
    for command in commands:
        proc = subprocess.Popen(command, shell=True)
        resp = proc.communicate()[0]
        proc.terminate()

    if BUILD_MFEATS:
        src = os.path.abspath(r'dist\mfeats\mfeats.exe')
        dst = os.path.abspath(r'dist\macrobox')
        shutil.copy(src, dst)
    src = os.path.abspath(r'dist\packages')
    dst = os.path.abspath(r'dist\macrobox\packages')
    shutil.copytree(src, dst)

    issc = r'''"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"'''
    command = '''%s "macrobox.iss"''' % (issc)
    proc = subprocess.Popen(command, shell=True)
    resp = proc.communicate()[0]
    proc.terminate()

    # https://www.comodossl.co.kr/certificate/code-signing-products.aspx
    # https://products.verisign.com/orders/enrollment/winqualOrder.do?change_lang=10

    # makecert.exe -sv macrobox.pvk -n "CN=MUTEKLAB" macrobox.cer -r
    # pvk2pfx.exe -pvk macrobox.pvk -spc macrobox.cer -pfx macrobox.pfx -po muteklab

    # command = '''signtool.exe sign /f "E:\XRESEARCHX\macroboxpro\dist\macrobox.pfx" /p muteklab /du "http://muteklab.com/*" "E:\XRESEARCHX\macroboxpro\dist\setup.exe"'''
    # proc = subprocess.Popen(command, shell=True)
    # resp = proc.communicate()[0]; proc.terminate()

    # http://stackoverflow.com/questions/16082333/why-i-get-the-specified-pfx-password-is-not-correct-when-trying-to-sign-applic

    # makecert.exe -sv macrobox.pvk -n "CN=macroboxplayer" macrobox.cer -r
    # pvk2pfx.exe -pvk macrobox.pvk -spc macrobox.cer -pfx macrobox.pfx -po muteklab
    # "C:\Program Files\Inno Setup 5\iscc" "/sStandard=C:\Program Files\Microsoft Visual Studio 8\SDK\v2.0\Bin\signtool.exe sign /f CertPath\mycert.pfx /p MyPassword $p" sfquery.iss
    # "C:\Program Files (x86)\Microsoft SDKs\Windows\v7.1A\Bin\signtool.exe"
    # http://msdn.microsoft.com/ko-kr/library/8s9b9yaz(v=vs.80).aspx
    # https://bytescout.com/support/index.php?_m=knowledgebase&_a=viewarticle&kbarticleid=296

    # issc = r'''"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"'''
    # signtool = r'''"/sStandard=C:\Program Files (x86)\Microsoft SDKs\Windows\v7.1A\Bin\signtool.exe sign /f dist\macrobox.pfx /p muteklab $p"'''
    # command = '''%s %s "macrobox.iss"''' % (issc, signtool)
    # proc = subprocess.Popen(command, shell=True)
    # resp = proc.communicate()[0]; proc.terminate()

    # issc = r'''"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"'''
    # # signtool = r'''"/sStandard=C:\Program Files (x86)\Microsoft SDKs\Windows\v7.1A\Bin\signtool.exe sign /f dist\macrobox.pfx /p muteklab $p"'''
    # command = '''signtool.exe sign /f "E:\XRESEARCHX\macroboxpro\dist\macrobox.pfx" /p muteklab /du "http://muteklab.com/" "E:\XRESEARCHX\macroboxpro\dist\setup.exe"'''
    # # command = '''%s %s "macrobox.iss"''' % (issc, signtool)
    # proc = subprocess.Popen(command, shell=True)
    # resp = proc.communicate()[0]; proc.terminate()

    # issc = r'''"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"'''
    # command = '''%s "macrobox.iss"''' % (issc)
    # proc = subprocess.Popen(command, shell=True)
    # resp = proc.communicate()[0]; proc.terminate()

    # path = os.path.abspath(r'''C:\Program Files (x86)\MacroBox''')
    # shutil.rmtree(path)


if __name__ == '__main__':
    main()
