# macOSでの起動とKaliからの接続

このマシンはNATやポート転送を使用しません。QEMUの`vmnet-bridged`とKaliを同じL2セグメントへ接続するため、TCP/UDPを問わず、ターゲット上のすべてのポートをKaliから探索できます。

ダウンロードした配布物を空の専用ディレクトリへ置き、展開します。

```sh
brew install qemu
unzip ARTIFACT_ID.zip
cd slsg-machine
```

## 前提

- Homebrew版QEMU
- 4 GiB以上の空きメモリ
- Kaliと共有する隔離ネットワーク
- `image.qcow2`、このREADME、`start-macos.sh`を同じディレクトリへ配置

## Apple Silicon上でx86_64マシンを起動

```sh
chmod +x start-macos.sh
networksetup -listallhardwareports
./start-macos.sh --bridge en1
```

誤って通常利用中のLANへ脆弱なマシンを公開しないよう、ブリッジ先は必須引数です。Kaliと共有する隔離Ethernetインターフェースを指定してください。

vmnetの権限エラーになる環境では、QEMUのパスを維持して管理者権限で実行します。

```sh
sudo env PATH="$PATH" ./start-macos.sh --bridge en1
```

Apple Siliconではx86_64ゲストをハードウェア仮想化できないため、QEMU TCGでCPUをエミュレーションします。Intel MacではHVFを使用します。起動後、ログインプロンプトの前にターゲットのIPv4アドレスが表示されます。ログインユーザーは`provisioner`、パスワードはマシンのダウンロード画面に表示された値です。

## VMware Fusion上のKali

Kaliのネットワークアダプターを「ブリッジ」にし、`start-macos.sh`の`--bridge`と同じ物理インターフェースを選択します。「自動検出」では異なるインターフェースが選ばれることがあるため、対象を明示することを推奨します。

## VirtualBox上のKali

Kaliの「ネットワーク」で「ブリッジアダプター」を選び、`start-macos.sh`の`--bridge`と同じインターフェースを指定します。

## Kaliから探索・接続

コンソールに表示されたIPをそのまま指定します。Mac側の転送ポートは使用しません。

```sh
sudo arp-scan --localnet
sudo nmap -Pn -sS -sV -p- TARGET_IP
sudo nmap -Pn -sU --top-ports 100 TARGET_IP
ssh provisioner@TARGET_IP
```

Wi-Fiアクセスポイントのクライアント分離や、無線NICのブリッジ制限により、VM同士が通信できない場合があります。その場合は専用の有線Ethernetアダプターを使用し、QEMUとKaliの両方をそのインターフェースへブリッジしてください。

## 注意

脆弱なサービスを企業LAN、公衆Wi-Fi、インターネットへ接続しないでください。専用の隔離有線LANを推奨します。終了はゲスト内で`sudo poweroff`を実行します。
