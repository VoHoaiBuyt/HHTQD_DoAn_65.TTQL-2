param(
    [string]$DocxPath = (Join-Path (Resolve-Path ".").Path "reports\BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx"),
    [string]$PdfPath = (Join-Path (Resolve-Path ".").Path "reports\BaoCao_Nhom1_HTTQD_65.TTQL-Final.pdf")
)

$ErrorActionPreference = "Stop"
$word = $null
$doc = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0

    $doc = $word.Documents.Open($DocxPath)
    $null = $doc.Fields.Update()

    foreach ($toc in $doc.TablesOfContents) {
        $toc.Update()
    }
    foreach ($tof in $doc.TablesOfFigures) {
        $tof.Update()
    }

    $doc.Repaginate()
    $doc.Save()

    # wdExportFormatPDF = 17
    $doc.ExportAsFixedFormat($PdfPath, 17)
    Write-Output "WORD_UPDATE_OK: $DocxPath"
    Write-Output "PDF_EXPORT_OK: $PdfPath"
}
finally {
    if ($null -ne $doc) {
        try { $doc.Close([ref]$false) } catch {}
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($doc) | Out-Null
    }
    if ($null -ne $word) {
        try { $word.Quit([ref]$false) } catch {}
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
