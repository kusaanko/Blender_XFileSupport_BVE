# Blender_XFileSupport_BVE
Bve用に設計されたBlender用のXファイル入出力プラグイン  

対応Blenderバージョン:4.0.0以降  
動作確認Bveバージョン:5.8, 6.0  
strview5互換あり  

# 対応しているXファイルの機能
* 頂点
* 面
* 法線(インポート時には使用されません)
* マテリアル(スペキュラーは未対応)
* テクスチャ
* テキスト、バイナリ形式、バイナリ圧縮形式

# 対応しているBlenderの機能
* マテリアル
  * ノード未使用時の色
  * プリンシプルBSDFノード
  * テクスチャノード
  * ベースカラー
  * アルファ
  * 放射
* フラットシェード、スムースシェード
* モディファイアー(100％動作はしません。)

# 使い方・注意点
Wikiページを御覧ください。[Wiki](https://github.com/kusaanko/Blender_XFileSupport_BVE/wiki)

# インストール方法
<img src="for_readme/preference.jpg" width="500px"></img>  
編集>プリファレンスをクリックして設定画面を出します  
<img src="for_readme/install.jpg" width="500px"></img>  
アドオン->インストールをクリックします  
<img src="for_readme/install_addon.jpg" width="500px"></img>  
ダウンロードしたXFileSupport.pyを選択してアドオンをインストールをクリックします。
<img src="for_readme/check.jpg" width="500px;"></img>  
「DirectX」と検索してこのプラグインが有効になっていることを確認してください。

# ToDo
- CSV入力のサポート