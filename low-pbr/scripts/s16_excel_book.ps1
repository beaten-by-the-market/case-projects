param([string]$Book, [string]$Raw)
# s16 2단계: DataGuide 원본 파일의 시트를 셀째로 통합문서에 복사한다 (s16_excel_book.py 가 부른다).
# 시트 1~9행(설정)과 A·D열(코드·아이템)이 그대로 옮겨져, 통합문서 안에서도 A1 Refresh 로 다시 받을 수 있다.
# Windows PowerShell 5.1 에서 한글을 읽도록 UTF-8(BOM)으로 저장한다.
$ErrorActionPreference = "Stop"
function Say($m) { Write-Host ((Get-Date -Format "HH:mm:ss") + " " + $m) }

try { $xl = [Runtime.InteropServices.Marshal]::GetActiveObject("Excel.Application"); $own = $false }
catch { $xl = New-Object -ComObject Excel.Application; $own = $true }
$alerts = $xl.DisplayAlerts; $xl.DisplayAlerts = $false
$wb = $xl.Workbooks.Open($Book)
$anchor = $wb.Worksheets.Item("업종")

function Copy-In([string]$file, [string]$name) {
  $open = $xl.Workbooks | Where-Object { $_.FullName -eq $file } | Select-Object -First 1   # 이미 열린 파일은 닫지 않는다
  $src = if ($open) { $open } else { $xl.Workbooks.Open($file, 0, $true) }
  $src.Worksheets.Item(1).Copy($anchor)
  $ws = $wb.Worksheets.Item($anchor.Index - 1)
  $ws.Name = $name
  if (-not $open) { $src.Close($false) }
  Say ("{0} ← {1} (마지막 행 {2}, 마지막 열 {3})" -f $name, (Split-Path $file -Leaf),
       $ws.UsedRange.Rows.Count, $ws.UsedRange.Columns.Count)
  return $ws
}

Copy-In (Join-Path $Raw "DG_시총.xlsx") "DG_시총" | Out-Null
Copy-In (Join-Path $Raw "DG_자본_회계기준.xlsx") "DG_자본" | Out-Null

# 기준일 목록 = 회차 시트 기준일 열
$rs = $wb.Worksheets.Item("회차")
$col = 0; for ($j = 1; $j -le 10; $j++) { if ($rs.Cells.Item(1, $j).Text -eq "기준일") { $col = $j } }
$dates = @(); for ($i = 2; $rs.Cells.Item($i, $col).Text -ne ""; $i++) { $dates += $rs.Cells.Item($i, $col).Text }
$ranges = Get-ChildItem $Raw -Filter "DG_상태_*-*.xlsx" | Select-Object -ExpandProperty FullName

foreach ($d in $dates) {
  $one = Join-Path $Raw ("DG_상태_{0}.xlsx" -f $d)
  if (Test-Path $one) { Copy-In $one ("DG_상태_" + $d) | Out-Null; continue }
  $iso = "{0}-{1}-{2}" -f $d.Substring(0, 4), $d.Substring(4, 2), $d.Substring(6, 2)
  $done = $false
  foreach ($f in $ranges) {
    $ws = Copy-In $f ("DG_상태_" + $d)
    $last = $ws.Cells.Item(9, $ws.Columns.Count).End(-4159).Column
    $hit = 0; for ($j = 7; $j -le $last; $j++) { if ($ws.Cells.Item(9, $j).Text -eq $iso) { $hit = $j; break } }
    if ($hit -eq 0) { $ws.Delete(); continue }
    # 그 날짜 열만 남기고 기간을 그 하루로 (B8=C8) — 기준일 하루로 받은 시트와 같은 모양
    if ($hit -lt $last) { $ws.Range($ws.Cells.Item(1, $hit + 1), $ws.Cells.Item(1, $last)).EntireColumn.Delete() | Out-Null }
    if ($hit -gt 7) { $ws.Range($ws.Cells.Item(1, 7), $ws.Cells.Item(1, $hit - 1)).EntireColumn.Delete() | Out-Null }
    $ws.Range("B8").Value2 = [double]$d; $ws.Range("C8").Value2 = [double]$d
    Say ("  {0}: 기간 파일에서 그 날짜 열만 남김 (G9={1})" -f $d, $ws.Range("G9").Text)
    $done = $true; break
  }
  if (-not $done) { throw "기준일 $d 상태 파일 없음" }
}

$wb.Worksheets.Item("안내").Activate()
$wb.Save()
Say ("저장: {0} (시트 {1}장)" -f $Book, $wb.Worksheets.Count)
$wb.Close($false)
$xl.DisplayAlerts = $alerts
if ($own) { $xl.Quit() }
