Add-Type -AssemblyName System.Drawing
$assetDir = Join-Path $PSScriptRoot 'assets'
[System.IO.Directory]::CreateDirectory($assetDir) | Out-Null
$bitmap = [System.Drawing.Bitmap]::new(256,256)
$g = [System.Drawing.Graphics]::FromImage($bitmap)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)
$paper = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#FFE18A'))
$dark = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#31564B'))
$fold = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#E7AF39'))
$path = [System.Drawing.Drawing2D.GraphicsPath]::new()
$path.AddArc(22,26,40,40,180,90)
$path.AddLine(42,26,194,26)
$path.AddArc(174,26,40,40,270,90)
$path.AddLine(214,46,214,178)
$path.AddLine(214,178,166,226)
$path.AddLine(166,226,42,226)
$path.AddArc(22,186,40,40,90,90)
$path.CloseFigure()
$g.FillPath($paper,$path)
$g.FillPolygon($fold,[System.Drawing.Point[]]@([System.Drawing.Point]::new(166,226),[System.Drawing.Point]::new(166,178),[System.Drawing.Point]::new(214,178)))
$pen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#9D7838'),10)
$pen.StartCap = $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$g.DrawLine($pen,56,112,132,112)
$g.DrawLine($pen,56,144,142,144)
$g.DrawLine($pen,56,176,112,176)
$g.FillEllipse($dark,151,16,64,26)
$g.FillRectangle($dark,166,29,34,47)
$g.FillPolygon($dark,[System.Drawing.Point[]]@([System.Drawing.Point]::new(150,89),[System.Drawing.Point]::new(166,65),[System.Drawing.Point]::new(200,65),[System.Drawing.Point]::new(216,89)))
$pinPen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#31564B'),9)
$g.DrawLine($pinPen,183,85,183,119)
$bitmap.Save((Join-Path $assetDir 'note.png'),[System.Drawing.Imaging.ImageFormat]::Png)
foreach ($size in @(16,24,32,48,64,128,256)) {
    $small = [System.Drawing.Bitmap]::new($size,$size)
    $sg = [System.Drawing.Graphics]::FromImage($small)
    $sg.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $sg.DrawImage($bitmap,0,0,$size,$size)
    $small.Save((Join-Path $assetDir "note-$size.png"),[System.Drawing.Imaging.ImageFormat]::Png)
    $sg.Dispose(); $small.Dispose()
}
$g.Dispose(); $bitmap.Dispose(); $paper.Dispose(); $dark.Dispose(); $fold.Dispose(); $pen.Dispose(); $pinPen.Dispose(); $path.Dispose()
