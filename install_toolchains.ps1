#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs missing language toolchains for VPyD's 14-engine execution matrix.

.DESCRIPTION
    Checks which runtimes/compilers are already on PATH, then installs the
    missing ones via winget (preferred) or direct download.

    Run from an elevated PowerShell:
        Set-ExecutionPolicy Bypass -Scope Process -Force
        .\install_toolchains.ps1

.NOTES
    Already installed tools are skipped automatically.
    After installation, restart your terminal / VS Code so PATH updates take effect.
#>

$ErrorActionPreference = 'Continue'

# ── Helper ──────────────────────────────────────────────────────────────────
function Test-Command($cmd) { $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue) }

function Install-If-Missing {
    param(
        [string]$Name,
        [string]$TestCmd,
        [string]$WingetId,
        [string]$FallbackUrl = '',
        [string]$FallbackNote = ''
    )

    if (Test-Command $TestCmd) {
        Write-Host "  [OK]  $Name  ($TestCmd already on PATH)" -ForegroundColor Green
        return
    }

    if ($WingetId -and (Test-Command 'winget')) {
        Write-Host "  [INSTALL]  $Name via winget ($WingetId) ..." -ForegroundColor Yellow
        winget install --id $WingetId --accept-source-agreements --accept-package-agreements --silent
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [DONE]  $Name installed." -ForegroundColor Green
        } else {
            Write-Host "  [WARN]  winget returned exit code $LASTEXITCODE for $Name" -ForegroundColor Red
            if ($FallbackNote) { Write-Host "          $FallbackNote" -ForegroundColor DarkYellow }
        }
    } elseif ($FallbackUrl) {
        Write-Host "  [MANUAL]  $Name — winget not available. Download from:" -ForegroundColor Magenta
        Write-Host "            $FallbackUrl"
    } else {
        Write-Host "  [SKIP]  $Name — no automated installer available." -ForegroundColor DarkGray
        if ($FallbackNote) { Write-Host "          $FallbackNote" -ForegroundColor DarkYellow }
    }
}

# ── Banner ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  VPyD Toolchain Installer — 14-Engine Execution Matrix" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Checking & installing missing language runtimes..." -ForegroundColor White
Write-Host ""

# ── Already installed (expected) ────────────────────────────────────────────
Write-Host "--- Core (likely already present) ---" -ForegroundColor DarkCyan
Install-If-Missing -Name "Python"      -TestCmd "python"  -WingetId "Python.Python.3.12"   -FallbackUrl "https://python.org"
Install-If-Missing -Name "Node.js"     -TestCmd "node"    -WingetId "OpenJS.NodeJS.LTS"     -FallbackUrl "https://nodejs.org"

# ── Compilers & Runtimes ───────────────────────────────────────────────────
Write-Host ""
Write-Host "--- Compilers & Runtimes ---" -ForegroundColor DarkCyan

Install-If-Missing -Name "Rust (rustc)" `
    -TestCmd "rustc" `
    -WingetId "Rustlang.Rustup" `
    -FallbackUrl "https://rustup.rs" `
    -FallbackNote "After install run: rustup default stable"

Install-If-Missing -Name "GCC (C/C++ via MinGW-w64)" `
    -TestCmd "gcc" `
    -WingetId "MSYS2.MSYS2" `
    -FallbackUrl "https://www.msys2.org" `
    -FallbackNote "After MSYS2 install, run in MSYS2 shell: pacman -S mingw-w64-x86_64-gcc && add C:\msys64\mingw64\bin to PATH"

Install-If-Missing -Name "Go" `
    -TestCmd "go" `
    -WingetId "GoLang.Go" `
    -FallbackUrl "https://go.dev/dl/"

Install-If-Missing -Name "Java (JDK)" `
    -TestCmd "javac" `
    -WingetId "Microsoft.OpenJDK.21" `
    -FallbackUrl "https://learn.microsoft.com/en-us/java/openjdk/download"

Install-If-Missing -Name "Ruby" `
    -TestCmd "ruby" `
    -WingetId "RubyInstallerTeam.RubyWithDevKit.3.3" `
    -FallbackUrl "https://rubyinstaller.org"

Install-If-Missing -Name "R (Rscript)" `
    -TestCmd "Rscript" `
    -WingetId "RProject.R" `
    -FallbackUrl "https://cran.r-project.org/bin/windows/base/"

Install-If-Missing -Name ".NET SDK (C#)" `
    -TestCmd "dotnet" `
    -WingetId "Microsoft.DotNet.SDK.8" `
    -FallbackUrl "https://dotnet.microsoft.com/download"

Install-If-Missing -Name "Kotlin" `
    -TestCmd "kotlinc" `
    -WingetId "JetBrains.Kotlin.Compiler" `
    -FallbackUrl "https://kotlinlang.org/docs/command-line.html" `
    -FallbackNote "Requires JDK. Also installable via SDKMAN or Homebrew."

Install-If-Missing -Name "Swift" `
    -TestCmd "swift" `
    -WingetId "Swift.Toolchain" `
    -FallbackUrl "https://www.swift.org/install/windows/" `
    -FallbackNote "Swift on Windows requires Visual Studio Build Tools."

# ── TypeScript runners ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- TypeScript Runners (npm packages) ---" -ForegroundColor DarkCyan

if (Test-Command 'tsx') {
    Write-Host "  [OK]  tsx already installed" -ForegroundColor Green
} elseif (Test-Command 'ts-node') {
    Write-Host "  [OK]  ts-node already installed (tsx preferred but ts-node works)" -ForegroundColor Green
} elseif (Test-Command 'npm') {
    Write-Host "  [INSTALL]  tsx via npm ..." -ForegroundColor Yellow
    npm install -g tsx
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [DONE]  tsx installed globally." -ForegroundColor Green
    } else {
        Write-Host "  [WARN]  npm install tsx failed. Try manually: npm install -g tsx" -ForegroundColor Red
    }
} else {
    Write-Host "  [SKIP]  tsx — npm not available (install Node.js first)" -ForegroundColor DarkGray
}

# ── Bash ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- Shell ---" -ForegroundColor DarkCyan
Install-If-Missing -Name "Bash (Git Bash)" `
    -TestCmd "bash" `
    -WingetId "Git.Git" `
    -FallbackUrl "https://git-scm.com/downloads" `
    -FallbackNote "Git for Windows includes Git Bash."

# ── Post-install: MSYS2 gcc note ───────────────────────────────────────────
if (-not (Test-Command 'gcc')) {
    Write-Host ""
    Write-Host "NOTE: If MSYS2 was just installed, open an MSYS2 MINGW64 shell and run:" -ForegroundColor Yellow
    Write-Host '  pacman -S --noconfirm mingw-w64-x86_64-gcc' -ForegroundColor White
    Write-Host "  Then add C:\msys64\mingw64\bin to your system PATH." -ForegroundColor White
}

# ── Post-install: Rust note ────────────────────────────────────────────────
if (-not (Test-Command 'rustc') -and (Test-Command 'rustup')) {
    Write-Host ""
    Write-Host "NOTE: rustup was installed but rustc may not be on PATH yet. Run:" -ForegroundColor Yellow
    Write-Host '  rustup default stable' -ForegroundColor White
}

# ── Summary ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Post-install checklist" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. RESTART your terminal / VS Code so PATH updates take effect." -ForegroundColor White
Write-Host "  2. Verify with:  python -c ""import shutil; [print(c, shutil.which(c)) for c in ['python','node','rustc','bash','gcc','g++','go','javac','ruby','Rscript','dotnet','kotlinc','swift','tsx']]""" -ForegroundColor DarkGray
Write-Host ""

# ── Final scan ──────────────────────────────────────────────────────────────
Write-Host "Current status:" -ForegroundColor White
$engines = @(
    @("Python",     "python"),
    @("Node.js",    "node"),
    @("TypeScript", "tsx"),
    @("Rust",       "rustc"),
    @("Java",       "javac"),
    @("Swift",      "swift"),
    @("C++ (g++)",  "g++"),
    @("R",          "Rscript"),
    @("Go",         "go"),
    @("Ruby",       "ruby"),
    @("C# (.NET)",  "dotnet"),
    @("Kotlin",     "kotlinc"),
    @("C (gcc)",    "gcc"),
    @("Bash",       "bash")
)

$ready = 0
$missing = 0
foreach ($e in $engines) {
    $name = $e[0]
    $cmd  = $e[1]
    if (Test-Command $cmd) {
        Write-Host "  [YES]  $name" -ForegroundColor Green
        $ready++
    } else {
        Write-Host "  [ - ]  $name" -ForegroundColor Red
        $missing++
    }
}

Write-Host ""
Write-Host "  $ready / $($ready + $missing) engines ready." -ForegroundColor $(if ($missing -eq 0) { 'Green' } else { 'Yellow' })
Write-Host ""
