# https://github.com/kusaanko/Blender_XFileSupport_BVE
#
# Copyright (c) 2021 kusaanko
# This is licensed under GPL v3.0 or later
# see https://github.com/kusaanko/Blender_XFileSupport_BVE/blob/main/LICENSE

import bpy
from .export_csv import ExportCSVFile
from .direct_x import ExportDirectXXFile, ImportDirectXXFile

# locale
#    (target_context, key): translated_str
translations_dict = {
    "ja_JP": {
        ("*", "Remove All Objects and Materials"): "全てのオブジェクトとマテリアルを削除する",
        ("*", "Gamma correction"): "ガンマ補正",
        ("*", "This file is not X file!"): "このファイルはXファイルではありません！",
        ("*", "Output mode"): "出力モード",
        ("*", "Binary"): "バイナリ",
        ("*", "Text mode"): "テキストモード",
        ("*", "Binary mode"): "バイナリモード",
        ("*", "Binary + Compress"): "バイナリ+圧縮",
        ("*", "Compressed binary mode"): "圧縮したバイナリモード",
        ("*", "Export material name"): "マテリアル名を出力する",
        ("*", "Export onyl selected objects"): "選択したオブジェクトのみエクスポート",
        ("*", "Export only necessary data"): "必要なデータのみエクスポート",
        ("*", "Gamma correction is not 2.2"): "ガンマ補正は2.2である必要があります",
        ("*", "This plug-in is for Bve. So some features are not supported."): "このプラグインはBve向けです。そのため、一部の機能はサポートされていません。",
        ("*", "For OpenBVE"): "OpenBVE向け",
        ("*", "Decal transparent color"): "テクスチャの透過色",
    }
}

# メニューに追加 / Add to the menu
def menu_func_import(self, context):
    self.layout.operator(ImportDirectXXFile.bl_idname, text="DirectX XFile (.x) for BVE")


def menu_func_export(self, context):
    self.layout.operator(ExportDirectXXFile.bl_idname, text="DirectX XFile (.x) for BVE")
    self.layout.operator(ExportCSVFile.bl_idname, text="CSV (.csv) for BVE")

classes = (
    ImportDirectXXFile,
    ExportDirectXXFile,
    ExportCSVFile,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    bpy.app.translations.register(__name__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__name__)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
