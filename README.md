# XFileSupport_BVE
Bve用に設計されたBlender用のXファイル入出力アドオン

CSV出力にも対応しています。また、OpenBVE専用のCSV機能にも対応します。

Blender Import / Export add-on for Bve

Exporting to CSV is also supported. Some OpenBVE features are supported.

対応Blenderバージョン / Supported Blender version:4.3.0以降  
動作確認Bveバージョン / Tested Bve versions:5.8, 6.0  
strview5互換あり / strview5 tested  
csvview5互換あり / csvview5 tested  

# Supported x file features / 対応しているXファイルの機能 
* Vertices / 頂点
* Faces / 面
* Normals (Not used when import) / 法線(インポート時には使用されません)
* Material / マテリアル
* Texture / テクスチャ
* Text, binary and zipped-binary file format / テキスト、バイナリ形式、バイナリ圧縮形式
* Frame

# Supported csv file features / 対応しているCSVファイルの機能
* All / 全て

# Supported Blender features / 対応しているBlenderの機能
* Material / マテリアル
  * Color without nodes / ノード未使用時の色
  * Precinple BSDF nodes / プリンシプルBSDFノード
  * Texture nodes / テクスチャノード
  * Base color / ベースカラー
  * Alpha / アルファ
  * Emission / 放射
  * Gamma / ガンマ
* Flat shade and Smooth shade / フラットシェード、スムースシェード
* Modifier ( Doesn't work completely ) / モディファイアー(100％動作はしません。)

# 使い方・注意点
Wikiページを御覧ください。[Wiki](https://github.com/kusaanko/XFileSupport_BVE/wiki)

# インストール方法
<img src="for_readme/preference.jpg" width="500px"></img>  
編集>プリファレンスをクリックして設定画面を出します  
<img src="for_readme/install.jpg" width="500px"></img>  
アドオン->インストールをクリックします  
<img src="for_readme/install_addon.jpg" width="500px"></img>  
ダウンロードしたXFileSupport.pyを選択してアドオンをインストールをクリックします。
<img src="for_readme/check.jpg" width="500px;"></img>  
「DirectX」と検索してこのプラグインが有効になっていることを確認してください。

# ビルド / Build

```
blender --command extension build --output-dir ../out
```

# 開発 / Development
bpyパッケージを導入したvenv環境下で補完を利かせながら開発することをお勧めします。

```
python -m venv .venv
./.venv/Scripts/activate
pip install bpy
```

# ToDo
- CSV入力のサポート
