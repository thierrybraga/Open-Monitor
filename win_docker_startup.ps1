param(
  [switch]$NoCache
)
$ErrorActionPreference = 'Stop'

function Show-Header {
  Write-Host "`n=== Open-Monitor | Docker Windows Startup ===" -ForegroundColor Cyan
}

function Test-Prerequisites {
  Write-Host "[pré-requisitos] Verificando Docker e Compose" -ForegroundColor Yellow
  try {
    $dv = docker --version
    $cv = docker compose version
    Write-Host "Docker: $dv" -ForegroundColor Green
    Write-Host "Compose: $cv" -ForegroundColor Green
    return $true
  } catch {
    Write-Host "❌ Docker/Compose não encontrados ou inacessíveis" -ForegroundColor Red
    Write-Host "Instale Docker Desktop e habilite Docker Compose." -ForegroundColor Red
    return $false
  }
}

function Wait-ServiceHealthy([string[]]$Services, [int]$TimeoutSec = 180) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $arr = docker compose ps --format json | ConvertFrom-Json
      $allOk = $true
      foreach ($svc in $Services) {
        $item = $arr | Where-Object { $_.Service -eq $svc }
        if (-not $item) { $allOk = $false; break }
        $cname = $item.Name
        $h = docker inspect $cname --format '{{json .State.Health}}' | ConvertFrom-Json
        if (-not $h -or $h.Status -ne 'healthy') { $allOk = $false; break }
      }
      if ($allOk) {
        foreach ($svc in $Services) { Write-Host "✅ Serviço saudável: $svc" -ForegroundColor Green }
        return $true
      }
    } catch {}
    Start-Sleep -Seconds 3
  }
  Write-Host "⚠️ Timeout aguardando saúde de serviços: $($Services -join ', ')" -ForegroundColor Yellow
  return $false
}

function Wait-AppHealthy([string]$BaseUrl = 'http://localhost:4443', [int]$TimeoutSec = 300) {
  Write-Host "[health] Aguardando aplicação em $BaseUrl" -ForegroundColor Yellow
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    try {
      $bootstrap = Invoke-RestMethod -Uri "$BaseUrl/api/v1/system/bootstrap" -Method GET -TimeoutSec 8
      if ($bootstrap -and $bootstrap.has_active_user -ne $null) {
        Write-Host "✅ App saudável" -ForegroundColor Green
        return $bootstrap
      }
    } catch {}
  }
  Write-Host "⚠️ Timeout aguardando saúde da aplicação" -ForegroundColor Yellow
  return $null
}

function Start-Test-Clean {
  Write-Host "[teste] Clean startup: containers e volumes serão removidos" -ForegroundColor Cyan
  try { docker compose down -v --remove-orphans | Out-Null } catch {}

  if ($NoCache) {
    Write-Host "[teste] Rebuild sem cache" -ForegroundColor Yellow
    $env:DOCKER_BUILDKIT = "1"
    $env:COMPOSE_DOCKER_CLI_BUILD = "1"
    try { docker compose build --no-cache } catch {}
  }

  Write-Host "[teste] Subindo stack (postgres_core, postgres_public, redis, app)" -ForegroundColor Cyan
  docker compose up -d --build
  $ok = Wait-ServiceHealthy -Services @('postgres_core','postgres_public','redis','app') -TimeoutSec 240
  $bs = Wait-AppHealthy -BaseUrl 'http://localhost:4443' -TimeoutSec 300
  if (-not $ok -or -not $bs) { return $false }
  Write-Host "[teste] Próximo passo:" -ForegroundColor Green
  if (-not $bs.has_active_user) {
    Write-Host " - Crie o root em http://localhost:4443/auth/init-root" -ForegroundColor Green
  } elseif (-not $bs.first_sync_completed) {
    Write-Host " - Acompanhe a sync: http://localhost:4443/loading" -ForegroundColor Green
  } else {
    Write-Host " - Sistema pronto: http://localhost:4443/" -ForegroundColor Green
  }
  return $true
}

function Start-Test-Existing {
  Write-Host "[teste] Iniciando ambiente existente" -ForegroundColor Cyan
  docker compose up -d
  $ok = Wait-ServiceHealthy -Services @('postgres_core','postgres_public','redis','app') -TimeoutSec 180
  $bs = Wait-AppHealthy -BaseUrl 'http://localhost:4443' -TimeoutSec 240
  return ($ok -and $bs)
}

function Start-Production {
  Write-Host "[produção] Subindo stack com rebuild" -ForegroundColor Cyan
  docker compose up -d --build
  $ok = Wait-ServiceHealthy -Services @('postgres_core','postgres_public','redis','app') -TimeoutSec 240
  $bs = Wait-AppHealthy -BaseUrl 'http://localhost:4443' -TimeoutSec 300
  if (-not $ok -or -not $bs) { return $false }
  Write-Host "[produção] Sistema pronto em http://localhost:4443" -ForegroundColor Green
  return $true
}

function Show-Menu {
  Show-Header
  Write-Host "Selecione uma opção:" -ForegroundColor Cyan
  Write-Host "  1) Novo ambiente de teste (clean startup)"
  Write-Host "  2) Ambiente de teste existente (iniciar)"
  Write-Host "  3) Verificação de pré-requisitos"
  Write-Host "  4) Ambiente de produção"
  Write-Host "  0) Sair"
}

Show-Menu
while ($true) {
  $choice = Read-Host "Opção"
  switch ($choice) {
    '1' {
      if (-not (Test-Prerequisites)) { break }
      $useNoCache = Read-Host "Rebuild sem cache? [y/N]"
      if ($useNoCache -match '^(y|Y|yes)$') { $NoCache = $true }
      if (Start-Test-Clean) { Write-Host "✔ Concluído" -ForegroundColor Green } else { Write-Host "✖ Falhou" -ForegroundColor Red }
      break
    }
    '2' {
      if (-not (Test-Prerequisites)) { break }
      if (Start-Test-Existing) { Write-Host "✔ Concluído" -ForegroundColor Green } else { Write-Host "✖ Falhou" -ForegroundColor Red }
      break
    }
    '3' {
      if (Test-Prerequisites) { Write-Host "✔ Ok" -ForegroundColor Green } else { Write-Host "✖ Falhou" -ForegroundColor Red }
    }
    '4' {
      if (-not (Test-Prerequisites)) { break }
      if (Start-Production) { Write-Host "✔ Concluído" -ForegroundColor Green } else { Write-Host "✖ Falhou" -ForegroundColor Red }
      break
    }
    '0' { break }
    default { Write-Host "Opção inválida" -ForegroundColor Yellow }
  }
}

exit 0

