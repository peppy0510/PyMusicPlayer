# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import os
import re
import shutil
import subprocess
import sys
import zipfile

from PIL import Image


# path = os.environ['PATH']
# os.environ['PATH'] = ';'.join([path, os.path.join(path.split(';')[0], 'Scripts')])


class BuildBase():

    class path():
        dist = 'dist'
        build = 'build'
        icondir = os.path.join('assets', 'icon')
        iconsrc = os.path.join(icondir, 'icon.png')
        icondst = os.path.join(icondir, 'icon.ico')
        mainsrc = os.path.join('source', 'main.pyw')
        spec = 'makebuild.spec'
        iss = 'makeinstaller.iss'
        winsxs = 'C:\\Windows\\WinSxS'
        pythondir = r'C:\\Program Files\\Python36'
        issc = r'C:\\Program Files (x86)\\Inno Setup 5\\ISCC.exe'

    @classmethod
    def remove_build(self):
        for path in [self.path.build, self.path.dist]:
            path = os.path.abspath(path)
            if os.path.isdir(path):
                try:
                    shutil.rmtree(path)
                    # print('removing %s' % (path))
                except Exception:
                    print('removing failed %s' % (path))

    @classmethod
    def make_icon(self):
        icon_sizes = [(v, v) for v in (16, 24, 32, 48, 64, 96, 128, 256,)]
        img = Image.open(self.path.iconsrc)
        if os.path.exists(self.path.icondst):
            os.remove(self.path.icondst)
        img.save(self.path.icondst, sizes=icon_sizes)

    @classmethod
    def subfile(self, ptrn, repl, path, **kwargs):
        if not os.path.exists(path):
            return

        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
            content = re.sub(ptrn, repl, content, **kwargs)

        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)

        return content

    @classmethod
    def get_info_from_source(self, key):
        ptrn = (r'''[_]{0,2}%s[_]{0,2}[\s]{0,}[=]{1}[\s]{0,}'''
                r'''['"]{1}([\w\d\.\-\s]{1,})['"]{1}''') % (key)
        with open(self.path.mainsrc, 'r') as file:
            content = file.read()
            m = re.search(ptrn, content)
            if m:
                return m.group(1)

    @classmethod
    def set_api_ms_win_crt_path(self, architecture='amd64'):
        # 'x86' or 'amd64'
        existing_dirs = []
        for dirname in os.listdir(self.path.winsxs):
            if not dirname.startswith(architecture):
                continue
            absdir = os.path.join(self.path.winsxs, dirname)
            if not os.path.isdir(absdir):
                continue

            for name in os.listdir(absdir):
                if 'api-ms-win-crt-' in name:
                    existing_dirs += [absdir]
        if not existing_dirs:
            return
        path = list(set(existing_dirs))[0]
        ptrn = (r'''(__api_ms_win_crt_path__[\s]{0,}=[\s]{0,}[\'\"]{1})'''
                r'''[\w\d\s\-\_\.\:\\]{0,}([\'\"]{1})''')
        path = path.replace('\\', '\\\\\\\\')
        self.subfile(ptrn, r'\g<1>{}\g<2>'.format(path), self.path.spec)

    @classmethod
    def set_default_python_path(self):
        path = self.path.pythondir
        ptrn = (r'''(__default_python_path__[\s]{0,}=[\s]{0,}[\'\"]{1})'''
                r'''[\w\d\s\-\_\.\:\\]{0,}([\'\"]{1})''')
        path = path.replace('\\', '\\\\')
        self.subfile(ptrn, r'\g<1>{}\g<2>'.format(path), self.path.spec)

    @classmethod
    def make_build(self):
        command = 'pyinstaller {}'.format(self.path.spec)
        proc = subprocess.Popen(command, shell=True)
        proc.communicate()

    @classmethod
    def make_installer(self):
        for name in os.listdir(self.path.dist):
            if os.path.splitext(name)[0][-1].isdigit():
                os.remove(os.path.join(self.path.dist, name))
        command = '"{}" "{}"'.format(self.path.issc, self.path.iss)
        proc = subprocess.Popen(command, shell=True)
        proc.communicate()

    @classmethod
    def run_build(self):
        name = self.get_appname()
        command = '"{}"'.format(os.path.join(self.path.dist, '{}.exe'.format(name)))
        proc = subprocess.Popen(command, shell=True)
        proc.communicate()

    @classmethod
    def get_installer_name(self):
        with open(self.path.iss, 'r') as file:
            for line in file.read().split('\n'):
                if 'OutputBaseFilename' in line:
                    return line.split('=')[-1].strip('" ')

    @classmethod
    def compress_installer(self):
        name = self.get_installer_name()
        if not name:
            return
        src_name = '{}.exe'.format(name)
        src_path = os.path.join(self.path.dist, src_name)
        dst_path = os.path.join(self.path.dist, '{}.zip'.format(name))
        file = zipfile.ZipFile(dst_path, 'w', zipfile.ZIP_DEFLATED)
        file.write(src_path, src_name)
        file.close()

    @classmethod
    def run_installer(self):
        name = self.get_installer_name()
        if not name:
            return
        command = '"{}"'.format(os.path.join(self.path.dist, name))
        proc = subprocess.Popen(command, shell=True)
        proc.communicate()


class Build(BuildBase):

    @classmethod
    def run(self, auto_build_info=True, run_installer=True):

        self.make_icon()

        if auto_build_info:

            self.set_dist()
            self.set_author()
            self.set_appname()
            self.set_version()

        self.set_api_ms_win_crt_path()
        self.set_default_python_path()
        self.remove_build()
        self.make_build()
        # # self.run_build()
        self.make_installer()
        self.compress_installer()

        if run_installer:
            self.run_installer()

    @classmethod
    def get_appname(self):
        return self.get_info_from_source('appname')

    @classmethod
    def get_version(self):
        return self.get_info_from_source('version')

    @classmethod
    def get_author(self):
        return self.get_info_from_source('author')

    @classmethod
    def set_appname(self):
        appname = self.get_appname()
        if appname:
            ptrn = (r'''(__appname__[\s]{0,}=[\s]{0,}[\'\"]{1})'''
                    r'''[\w\d\s\-\_\.]{0,}([\'\"]{1})''')
            self.subfile(ptrn, r'\g<1>{}\g<2>'.format(appname), self.path.spec)

            keys = r'|'.join([
                'AppName', 'AppVerName',
                'DefaultDirName', 'DefaultGroupName',
                'UninstallDisplayIcon', 'OutputBaseFilename', 'Name', 'Filename'])
            version_ptrn = r'[\d]{1,}\.[\d]{1,}\.[\d]{1,}'
            ptrn = (r'(%s)'
                    r'([\s]{0,}[\=\:]{1}[\s]{0,}\")'
                    r'(\{[a-z]{1,}\}\\){0,1}'
                    r'[\w\d\s]{1,}'
                    r'(|\.exe|[\s\-\_\.]{1}%s[\s\-\_\.]{0,}[\w\d]{0,})'
                    r'(\")') % (keys, version_ptrn)
            self.subfile(ptrn, r'\g<1>\g<2>\g<3>{}\g<4>\g<5>'.format(appname), self.path.iss)

    @classmethod
    def set_version(self):
        version = self.get_version()
        if version:
            ptrn = r'([\d]{1,}\.[\d]{1,}\.[\d]{1,})'
            self.subfile(ptrn, version, self.path.iss)

    @classmethod
    def set_author(self):
        author = self.get_author()
        if author:
            keys = r'|'.join([
                'AppCopyright', 'AppPublisher',
                'VersionInfoCompany', 'VersionInfoCopyright'])
            ptrn = r'(%s)([\s]{0,}=[\s]{0,}\")[\w\d\s\.\-\_]{1,}(\")' % (keys)
            self.subfile(ptrn, r'\g<1>\g<2>{}\g<3>'.format(author), self.path.iss)

    @classmethod
    def set_dist(self):
        ptrn = (r'(Source|OutputDir)'
                r'([\s]{0,}\:[\s]{0,}\")'
                r'[\w\d\s\.\-\_]{1,}'
                r'(\\\*){0,}'
                r'(\")')
        self.subfile(ptrn, r'\g<1>\g<2>{}\g<3>\g<4>'.format(self.path.dist), self.path.iss)

if __name__ == '__main__':
    from io import TextIOWrapper
    sys.stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    Build.run()
