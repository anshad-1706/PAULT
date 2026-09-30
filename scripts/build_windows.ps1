$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw "Python 3.11 or newer is required to build PAULT."
    }
    $Python = $PythonCommand.Source
}

Push-Location $ProjectRoot
try {
    & $Python -m pip install -e ".[portable-build]"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install the portable-build dependencies."
    }

    $DistDirectory = Join-Path $ProjectRoot "dist"
    $WorkDirectory = Join-Path $ProjectRoot "build\pyinstaller"
    $PyInstallerArguments = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name", "PAULT",
        "--paths", $ProjectRoot,
        "--distpath", $DistDirectory,
        "--workpath", $WorkDirectory,
        "--specpath", $WorkDirectory,
        "--collect-all", "argon2"
    )
    $LogoPath = Join-Path $ProjectRoot "pault_desktop\assets\pault_logo.png"
    if (!(Test-Path $LogoPath)) {
        throw "The official PAULT logo is missing: $LogoPath"
    }
    $IconPath = Join-Path $WorkDirectory "pault_logo.ico"
    New-Item -ItemType Directory -Path $WorkDirectory -Force | Out-Null
    & $Python -c "from PIL import Image; import sys; Image.open(sys.argv[1]).convert('RGBA').save(sys.argv[2], format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])" $LogoPath $IconPath
    if ($LASTEXITCODE -ne 0) {
        throw "Could not convert the supplied PAULT PNG to a Windows icon."
    }
    $PyInstallerArguments += @("--add-data", "$LogoPath;pault_desktop/assets", "--icon", $IconPath)
    $PyInstallerArguments += (Join-Path $PSScriptRoot "pault_entry.py")
    & $Python -m PyInstaller @PyInstallerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build PAULT."
    }

    $PortableDirectory = Join-Path $DistDirectory "PAULT"
    New-Item -ItemType Directory -Path (Join-Path $PortableDirectory "Vaults") -Force | Out-Null
    Write-Host "Portable PAULT build: $PortableDirectory"
    Write-Host "Run: $(Join-Path $PortableDirectory 'PAULT.exe')"
} finally {
    Pop-Location
}