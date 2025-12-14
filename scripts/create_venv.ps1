param(
  [string] $venvDir = ".venv",
  [string] $python = "python"
)

# create venv
& $python -m venv $venvDir
# upgrade pip
& "$venvDir\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
# install deps
& "$venvDir\Scripts\python.exe" -m pip install -r requirements.txt
Write-Host "Activate with: & $venvDir\Scripts\Activate.ps1"