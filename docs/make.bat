@ECHO OFF

set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=build

if "%1" == "" goto help
if "%1" == "html" goto html
if "%1" == "clean" goto clean

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR%
goto end

:html
%SPHINXBUILD% -b html %SOURCEDIR% %BUILDDIR%\html
echo Build finished. HTML pages are in %BUILDDIR%\html.
goto end

:clean
rmdir /s /q %BUILDDIR%
goto end

:end
