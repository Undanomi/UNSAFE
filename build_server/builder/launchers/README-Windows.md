# Windowsでの起動とKaliからの接続

このマシンはNATやポート転送を使用しません。QEMUのTAPアダプターとKaliを同じL2セグメントへ接続するため、TCP/UDPを問わず、ターゲット上のすべてのポートをKaliから探索できます。

ダウンロードした`<artifact_id>.zip`を展開します。

```powershell
Expand-Archive .\ARTIFACT_ID.zip -DestinationPath .
Set-Location .\slsg-machine
```

空の専用ディレクトリ内で展開することを推奨します。

## 前提

- x86_64版QEMU for Windows（`qemu-system-x86_64.exe`へPATHが通っていること）
- TAP-Windows6アダプター
- 4 GiB以上の空きメモリ
- `image.qcow2`、このREADME、`Start-Windows.ps1`を同じディレクトリへ配置

高速に実行する場合は「Windowsの機能」で`Windows Hypervisor Platform`を有効にして再起動します。PowerShellの実行が拒否される場合は、開いているウィンドウだけを対象に許可します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## TAPアダプターを準備

OpenVPNのTAP-Windows6ドライバーなどを導入し、`Get-NetAdapter`で名前を確認します。スクリプトの既定名は、従来の起動例と同じ`OpenVPN TAP-Windows6`です。

```powershell
Get-NetAdapter
```

「ネットワーク接続」でTAPアダプターと、Kaliが使用する隔離ネットワークのアダプターを選択し、「ブリッジ接続」を作成します。企業LANやインターネット側のアダプターとはブリッジしないでください。

## 起動

```powershell
.\Start-Windows.ps1
```

TAP名を変更した場合は明示します。

```powershell
.\Start-Windows.ps1 -TapAdapter "SLSG TAP"
```

WHPXを使用できない場合はTCGで起動できます。

```powershell
.\Start-Windows.ps1 -Accelerator tcg -TapAdapter "SLSG TAP"
```

起動後、ログインプロンプトの前にターゲットのIPv4アドレスが表示されます。ログインユーザーは`provisioner`、パスワードはマシンのダウンロード画面に表示された値です。

## VMware Workstation Pro上のKali

Virtual Network Editorで隔離用VMnetを作成し、KaliのNICをそのVMnetへ接続します。Windows側ではQEMUのTAPと、そのVMnetのホスト仮想アダプターをブリッジします。VMnetのDHCPを使用する場合は、ターゲットにも同じDHCPからアドレスが割り当てられることを確認してください。

## VirtualBox上のKali

VirtualBox Host-Onlyネットワークを作成し、KaliのNICをそのネットワークへ接続します。Windows側ではQEMUのTAPと、対応する`VirtualBox Host-Only Ethernet Adapter`をブリッジします。Host-Only DHCPを有効にしてください。

## WSL Kali

QEMUのTAPを専用の有線LANアダプターへブリッジし、WSL Kaliからコンソールに表示されたターゲットIPへ直接アクセスします。WSL2 NATからそのサブネットへの経路は通常Windowsが処理します。到達しない場合は、Windowsで対象サブネットへの経路と、WSLから隔離LANへの送信が許可されていることを確認してください。ポート転送へ切り替えるのではなく、L2セグメントまたは経路を修正してください。

## Kaliから探索・接続

コンソールに表示されたIPをそのまま指定します。Windows側の転送ポートは使用しません。

```sh
sudo arp-scan --localnet
sudo nmap -Pn -sS -sV -p- TARGET_IP
sudo nmap -Pn -sU --top-ports 100 TARGET_IP
ssh provisioner@TARGET_IP
```

IPが表示されない場合は、WindowsのネットワークブリッジにTAPとKali側アダプターの両方が所属していること、隔離ネットワークのDHCPがブリッジ越しに応答していることを確認してください。

## 注意

脆弱なサービスを企業LAN、公衆Wi-Fi、インターネットへ接続しないでください。専用のHost-Onlyネットワーク、隔離された仮想スイッチ、または物理的に隔離した有線LANを使用してください。終了はゲスト内で`sudo poweroff`を実行します。
