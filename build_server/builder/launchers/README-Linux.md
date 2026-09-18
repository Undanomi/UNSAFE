# Linuxでの起動とKaliからの接続

このマシンはNATやポート転送を使用しません。QEMUのTAPをKaliと同じL2セグメントへ接続するため、TCP/UDPを問わず、ターゲット上のすべてのポートをKaliから探索できます。

ダウンロードした配布物は、QEMUと`zstd`を導入したLinux上で展開します。

```sh
tar --zstd -xf slsg-machine.tar.zst
cd slsg-machine
```

アーカイブはカレントディレクトリへ直接展開されるため、空の専用ディレクトリ内で実行することを推奨します。

## 前提

- x86_64版QEMU（`qemu-system-x86_64`）
- 4 GiB以上の空きメモリ
- DHCPを利用できる隔離ブリッジ
- `image.qcow2`、このREADME、`start-linux.sh`を同じディレクトリへ配置

Debianでは次のようにQEMUを導入できます。

```sh
sudo apt update
sudo apt install qemu-system-x86 qemu-utils iproute2 zstd
```

## TAPを隔離ブリッジへ接続

以下では、Kaliが接続する既存の隔離ブリッジを`br-slsg`、QEMU用TAPを`tap-slsg`とします。`br-slsg`は、専用の有線NICやハイパーバイザーの隔離ネットワークへ接続し、DHCPがターゲットへ届くよう事前に構成してください。

```sh
sudo ip tuntap add dev tap-slsg mode tap user "$USER"
sudo ip link set tap-slsg master br-slsg
sudo ip link set tap-slsg up
```

再起動後も使用する場合は、使用中のNetworkManagerまたはsystemd-networkdへ同じ設定を登録してください。

## 起動

```sh
chmod +x start-linux.sh
./start-linux.sh
```

別名のTAPを使用する場合は指定できます。

```sh
./start-linux.sh --tap tap-scenario-1
```

利用できる場合はKVM、利用できなければTCGによるx86_64エミュレーションを自動選択します。起動後、ログインプロンプトの前にターゲットのIPv4アドレスが表示されます。ログインユーザーは`provisioner`、パスワードはマシンのダウンロード画面に表示された値です。

## VMware Workstation Pro上のKali

VMware Virtual Network EditorでKali用VMnetを`br-slsg`と同じ隔離ネットワークへブリッジし、KaliのNICをそのVMnetへ接続します。専用の有線LANを使う場合は、`br-slsg`とKaliのVMnetを同じ有線NICへブリッジします。

## VirtualBox上のKali

Kaliの「ネットワーク」設定で「ブリッジアダプター」を選び、名前に`br-slsg`または`br-slsg`が使用する専用NICを指定します。VirtualBox Host-Onlyを利用する場合は、そのネットワークとTAPが同じLinuxブリッジへ所属し、DHCPが動作している必要があります。

## WSL Kaliを別のWindows PCで使う場合

Windows PCを`br-slsg`が接続している隔離LANへ接続します。WSL Kaliからコンソールに表示されたターゲットIPへ直接アクセスします。Windows Defender Firewallでは、WSLから隔離LANへの送信が許可されていることを確認してください。

## Kaliから探索・接続

コンソールに表示されたIPをそのまま指定します。ホスト側の転送ポートは使用しません。

```sh
sudo arp-scan --localnet
sudo nmap -Pn -sS -sV -p- TARGET_IP
sudo nmap -Pn -sU --top-ports 100 TARGET_IP
ssh provisioner@TARGET_IP
```

ターゲットIPへ到達できない場合は、`ip link show master br-slsg`でTAPがブリッジに所属していること、Kaliとターゲットが同じサブネットのアドレスを取得していることを確認してください。

## 注意

脆弱なサービスを企業LAN、公衆Wi-Fi、インターネットへ接続しないでください。専用のHost-Onlyネットワーク、隔離された仮想スイッチ、または物理的に隔離した有線LANを使用してください。終了はゲスト内で`sudo poweroff`を実行します。
