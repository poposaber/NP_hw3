# Setup (dev)

1. Ensure Python 3.12+ is installed (use py -3.12 on Windows).
2. Create venv:
   - Windows PowerShell: .\scripts\create_venv.ps1
   - Linux/macOS: ./scripts/create_venv.sh
3. Activate:
   - PowerShell: .venv\Scripts\Activate.ps1
   - CMD: .venv\Scripts\activate.bat
   - POSIX: source .venv/bin/activate
4. Install Requirements:
   python -m pip install -r requirements.txt
5. Run: 
   - For developers: python -m clients.developer_client
   - For players: python -m clients.player_client