# Assemble showcase image assets from real-API captures and archived evidence.
$ErrorActionPreference = 'Stop'
$root = 'D:\hackerthon-bank-agent'
$showcase = Join-Path $root '.scratch\liangshuang-frontend-complete\showcase'
$assets = Join-Path $showcase 'assets'
$raw = Join-Path $showcase 'raw'
$reg = Join-Path $root '.scratch\liangshuang-frontend-complete\evidence\2026-10-21-replace-entry-and-regress'
$bills = Join-Path $root '.scratch\liangshuang-frontend-complete\evidence\2026-10-21-real-api-bills-slot'
$obs = Join-Path $root 'evals\transfer\evidence\2026-10-21\offline-react-full-20261021-browser'
New-Item -ItemType Directory -Force -Path $assets | Out-Null

$map = @(
  @($raw, 't01-welcome.png', 'transfer-welcome.png'),
  @($raw, 't02-confirmation.png', 'transfer-confirm.png'),
  @($raw, 't03-cancelled.png', 'transfer-cancelled.png'),
  @($raw, 't04-modify.png', 'transfer-modify.png'),
  @($raw, 't05-verification.png', 'transfer-verify.png'),
  @($raw, 't06-demo-code.png', 'transfer-demo-code.png'),
  @($raw, 'zz-verifyWrong-error.png', 'transfer-code-wrong.png'),
  @($raw, 't09-recovery-gate.png', 'transfer-recovery-gate.png'),
  @($raw, 't10-recovery-readable.png', 'transfer-recovery-readable.png'),
  @($raw, 't11-highrisk.png', 'transfer-highrisk.png'),
  @($raw, 'b01-summary-choice.png', 'bills-summary-choice.png'),
  @($raw, 'b02-summary-card.png', 'bills-summary.png'),
  @($raw, 'b03-detail-choice.png', 'bills-detail-choice.png'),
  @($raw, 'b04-detail-card.png', 'bills-detail.png'),
  @($raw, 'b05-anomaly-choice-range.png', 'bills-anomaly-range.png'),
  @($raw, 'b06-anomaly-choice-listing.png', 'bills-anomaly-listing.png'),
  @($raw, 'b07-anomaly-choice-account.png', 'bills-anomaly-account.png'),
  @($raw, 'b08-anomaly-choice-candidate.png', 'bills-anomaly-candidate.png'),
  @($raw, 'b09-anomaly-card.png', 'bills-anomaly-clear.png'),
  @($raw, 'b10-report-choice.png', 'bills-report-choice.png'),
  @($raw, 'b11-report-card.png', 'bills-report.png'),
  @($reg, '04-result.png', 'transfer-result.png'),
  @($reg, '05-reload-readonly.png', 'transfer-reload.png'),
  @($reg, 'route-root.png', 'route-root.png'),
  @($reg, 'route-legacy.png', 'route-legacy.png'),
  @($reg, '390-01-welcome.png', 'mobile-welcome.png'),
  @($reg, '390-02-confirmation.png', 'mobile-confirm.png'),
  @($reg, '390-03-verification.png', 'mobile-verify.png'),
  @($reg, '390-04-bills-summary.png', 'mobile-bills-summary.png'),
  @($reg, '390-05-bills-report.png', 'mobile-bills-report.png'),
  @($bills, '03-detail-transfer.png', 'bills-detail-transfer.png'),
  @($bills, '04-anomaly.png', 'bills-anomaly.png'),
  @($obs, 'TF-OBS-04.png', 'cross-restored.png'),
  @($obs, 'TF-OBS-06.png', 'cross-expired.png'),
  @($obs, 'TF-OBS-07.png', 'cross-stale.png')
)

$missing = @()
foreach ($item in $map) {
  $source = Join-Path $item[0] $item[1]
  $target = Join-Path $assets $item[2]
  if (Test-Path $source) {
    Copy-Item -LiteralPath $source -Destination $target -Force
  } else {
    $missing += $item[1]
  }
}

$existing = Get-ChildItem $assets -File | Sort-Object Name
Write-Host ("assets: {0} files, {1:N1} MB" -f $existing.Count, (($existing | Measure-Object Length -Sum).Sum / 1MB))
if ($missing.Count -gt 0) { Write-Host ("missing: " + ($missing -join ', ')) } else { Write-Host 'missing: none' }
