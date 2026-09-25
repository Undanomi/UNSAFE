# Windowsでの起動とKaliからの接続

Windows上のQEMUでマシンを起動し、VMware上のKali Linuxから接続します。

ダウンロードした `<ARTIFACT_ID>.zip` を展開します。

```powershell
Expand-Archive .\<ARTIFACT_ID>.zip -DestinationPath .
Set-Location .\slsg-machine
```

空の専用ディレクトリ内で展開することを推奨します。

## 前提

- x86_64版QEMU for Windows
- OpenVPNのTAP-Windows6アダプター
- VMware上で動作するKali Linux
- 4 GiB以上の空きメモリ
- `image.qcow2`、このREADME、`Start-Windows.ps1`を同じディレクトリへ配置

QEMUのインストール先を、Windowsの環境変数 `Path` に追加します。

```text
<QEMU_INSTALL_DIRECTORY>
```

標準的なインストール先の例は次のとおりです。

```text
C:\Program Files\qemu
```

PowerShellで次のコマンドを実行し、QEMUへPATHが通っていることを確認します。

```powershell
qemu-system-x86_64.exe --version
```

高速に実行する場合は「Windowsの機能」で `Windows Hypervisor Platform` を有効にして再起動します。

PowerShellの実行が拒否される場合は、開いているウィンドウだけを対象に許可します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## TAPアダプターを準備

OpenVPNのTAP-Windows6ドライバーなどを導入し、`Get-NetAdapter` でアダプター名を確認します。

```powershell
Get-NetAdapter
```

ネットワークアダプター名は環境によって異なります。以降の `<VMWARE_NAT_ADAPTER>` と `<TAP_ADAPTER>` は、実際に表示されている名前に置き換えてください。

例：

```text
<VMWARE_NAT_ADAPTER>: VMware Network Adapter VMnet8
<TAP_ADAPTER>: OpenVPN TAP-Windows6
```

`Windowsキー + R` を押し、次のコマンドを入力します。

```text
ncpa.cpl
```

「ネットワーク接続」で、Kali Linuxが使用するVMwareのNAT用ネットワークアダプターを右クリックし、「プロパティ」を開きます。

「共有」タブを選択し、「ネットワークのほかのユーザーに、このコンピューターのインターネット接続をとおしての接続を許可する」にチェックを入れます。

共有先には、OpenVPNのTAPアダプターを指定します。

企業LANや公衆Wi-Fiなど、外部ネットワーク側のアダプターを共有先に指定しないでください。

## 起動

PowerShellで、`Start-Windows.ps1` が配置されているディレクトリへ移動します。

```powershell
Set-Location "<MACHINE_DIRECTORY>"
```

起動スクリプトを実行します。

```powershell
.\Start-Windows.ps1
```

TAPアダプター名がスクリプトの既定値と異なる場合は、実際のアダプター名を指定します。

```powershell
.\Start-Windows.ps1 -TapAdapter "<TAP_ADAPTER>"
```

実行例：

```powershell
.\Start-Windows.ps1 -TapAdapter "OpenVPN TAP-Windows6"
```

WHPXを使用できない場合は、TCGで起動できます。

```powershell
.\Start-Windows.ps1 -Accelerator tcg -TapAdapter "<TAP_ADAPTER>"
```

起動後、ログインプロンプトの前にターゲットのIPv4アドレスが表示されます。

ここまでの操作はWindows上で行います。

## VMware Workstation Pro上のKali

VMware上のKali Linuxで、ネットワーク接続をNATに設定します。

NATを選択すると、通常は `VMware Network Adapter VMnet8` が使用されます。ただし、アダプター名は環境によって異なるため、Windowsの「ネットワーク接続」で実際の名前を確認してください。

Windows側では、VMwareのNAT用ネットワークアダプターの共有先に、QEMUが使用するTAPアダプターを指定します。

## VirtualBox上のKali

VirtualBox Host-Onlyネットワークを作成し、KaliのNICをそのネットワークへ接続します。

Windows側では、QEMUのTAPと、対応する `VirtualBox Host-Only Ethernet Adapter` を同じネットワークへ接続します。Host-Only DHCPを有効にしてください。

アダプター名は環境によって異なるため、実際に表示されている名前を確認してください。

## WSL Kali

QEMUのTAPを専用の有線LANアダプターへ接続し、WSL Kaliからコンソールに表示されたターゲットIPへアクセスします。

WSL2からターゲットへ到達しない場合は、Windowsで対象サブネットへの経路と、WSLから隔離LANへの送信が許可されていることを確認してください。

## Kaliから探索・接続確認

ここからの操作は、VMware上のKali Linuxで行います。

QEMUのコンソールに表示されたIPアドレスを `<TARGET_IP>` に指定します。

最初に、Kali Linuxからターゲットへpingを実行します。

```sh
ping <TARGET_IP>
```

応答が返れば、Kali Linuxからターゲットへの接続は成功です。

pingを終了する場合は、`Ctrl + C` を押します。

必要に応じて、ターゲットを探索します。

```sh
sudo arp-scan --localnet
sudo nmap -Pn -sS -sV -p- <TARGET_IP>
sudo nmap -Pn -sU --top-ports 100 <TARGET_IP>
```

IPアドレスが表示されない場合やpingの応答がない場合は、次の項目を確認してください。

- QEMU上でマシンが起動していること
- Kali Linuxのネットワーク接続がVMwareのNATになっていること
- VMwareのNAT用ネットワークアダプターの共有が有効になっていること
- 共有先にQEMUが使用するTAPアダプターを指定していること
- `Start-Windows.ps1` に指定したTAPアダプター名が正しいこと
- `<TARGET_IP>` にコンソールへ表示されたIPアドレスを指定していること

## 注意

脆弱なサービスを企業LAN、公衆Wi-Fi、インターネットへ接続しないでください。専用の隔離有線LANを推奨します。終了はゲスト内で `sudo poweroff` を実行します。