$repo = "deanhan2026-lang/silicon-civilization-kb"
$branch = "main"
$dir = "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb"

$files = @(
    "docs/zhihu_article_v8_blurred.md",
    "docs/patent_preliminary_review.md",
    "docs/patent_application_prep.md",
    "anti_drift/baseline_binding.py",
    "demos/m6_demo.py",
    "docs/molicamp_application_full.md"
)

Write-Host "Total files: $($files.Count)"

# Step 1: Get current commit SHA
$currentSHA = (gh api "repos/$repo/git/ref/heads/$branch" --jq '.object.sha').Trim()
Write-Host "Current SHA: $currentSHA"

# Step 2: Create blobs for all files
$treeEntries = @()
foreach ($file in $files) {
    $fp = Join-Path $dir $file
    if (-not (Test-Path $fp)) { Write-Host "  [SKIP] $file (not found)"; continue }
    
    $bytes = [System.IO.File]::ReadAllBytes($fp)
    $b64 = [Convert]::ToBase64String($bytes)
    $blobBody = @{content=$b64; encoding="base64"} | ConvertTo-Json -Compress
    $blobSHA = ($blobBody | gh api "repos/$repo/git/blobs" --input - --jq '.sha').Trim()
    
    $treeEntries += @{path=$file; mode="100644"; type="blob"; sha=$blobSHA}
    Write-Host "  [BLOB] $file -> $($blobSHA.Substring(0,8))"
}

# Step 3: Get base tree
$baseTree = (gh api "repos/$repo/git/commits/$currentSHA" --jq '.tree.sha').Trim()
Write-Host "Base tree: $baseTree"

# Step 4: Create tree with all files
$treeBody = @{base_tree=$baseTree; tree=$treeEntries} | ConvertTo-Json -Compress -Depth 10
$treeSHA = ($treeBody | gh api "repos/$repo/git/trees" --input - --jq '.sha').Trim()
Write-Host "New tree: $treeSHA"

# Step 5: Create commit
$commitBody = @{message="feat: Phase 2 docs - zhihu article v8 (blurred), patent prep, demo scripts"; tree=$treeSHA; parents=@($currentSHA)} | ConvertTo-Json -Compress -Depth 10
$newSHA = ($commitBody | gh api "repos/$repo/git/commits" --input - --jq '.sha').Trim()
Write-Host "New commit: $newSHA"

# Step 6: Update ref
$refBody = @{sha=$newSHA; force=$false} | ConvertTo-Json -Compress
$refBody | gh api "repos/$repo/git/refs/heads/$branch" --method PATCH --input - | Out-Null

Write-Host "=== DONE ==="
Write-Host "$($treeEntries.Count) files pushed in 1 commit"
