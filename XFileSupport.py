# https://github.com/kusaanko/Blender_XFileSupport_BVE
#
# Copyright (c) 2021 kusaanko
# This is licensed under the Apache License 2.0
# see https://github.com/kusaanko/Blender_XFileSupport_BVE/blob/main/LICENSE

import os
import re
import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.types import Panel, Operator
import urllib.request
import urllib.parse
import json
import webbrowser
import struct
import threading
import functools

bl_info = {
    "name": "Import/Export DirectX X File (.x) for Bve",
    "author": "kusaanko",
    "version": (2, 1, 0),
    "blender": (2, 83, 0),
    "location": "File > Import / Export > DirectX XFile(.x)",
    "description": "Import/Export files in the DirectX X file (.x)",
    "warning": "This plug-in is for Bve. So some features are not supported.",
    "wiki_url": "https://github.com/kusaanko/Blender_XFileSupport_BVE/wiki",
    "tracker_url": "",
    "category": "Import-Export"
}

__version__ = "2.2.0"

# locale
#    (target_context, key): translated_str
translations_dict = {
    "ja_JP": {
        ("*", "Remove All Objects and Materials"): "全てのオブジェクトとマテリアルを削除する",
        ("*", "The update of XFileSupport is available!"): "XFileSupportの更新が利用可能です！",
        ("*", "Your version:"): "現在のバージョン:",
        ("*", "New version:"): "新しいバージョン:",
        ("*", "Please download from this link."): "このリンクからダウンロードしてください。",
        ("*", "This file is not X file!"): "このファイルはXファイルではありません！",
        ("*", "Output mode"): "出力モード",
        ("*", "Binary"): "バイナリ",
        ("*", "Text mode"): "テキストモード",
        ("*", "Binary mode"): "バイナリモード",
        ("*", "Export material name"): "マテリアル名を出力する",
        ("*", "Export onyl selected objects"): "選択したオブジェクトのみエクスポート",
        ("*", "XFileSupport was updated to %s"): "XFileSupportは%sにアップデートされました。",
        ("*", "Please restart Blender to apply this update."): "この更新を適用するには、Blenderを再起動してください。",
    }
}

TOKEN_NAME = 1
TOKEN_STRING = 2
TOKEN_INTEGER = 3
TOKEN_GUID = 5
TOKEN_INTEGER_LIST = 6
TOKEN_FLOAT_LIST = 7

TOKEN_OBRACE = 0x0A
TOKEN_CBRACE = 0x0B
TOKEN_OPAREN = 0x0C
TOKEN_CPAREN = 0x0D
TOKEN_OBRACKET = 0x0E
TOKEN_CBRACKET = 0x0F
TOKEN_OANGLE = 0x10
TOKEN_CANGLE = 0x11
TOKEN_DOT = 0x12
TOKEN_COMMA = 0x13
TOKEN_SEMICOLON = 0x14
TOKEN_TEMPLATE = 0x1F
TOKEN_WORD = 0x28
TOKEN_DWORD = 0x29
TOKEN_FLOAT = 0x2A
TOKEN_DOUBLE = 0x2B
TOKEN_CHAR = 0x2C
TOKEN_UCHAR = 0x2D
TOKEN_SWORD = 0x2E
TOKEN_SDWORD = 0x2F
TOKEN_VOID = 0x30
TOKEN_LPSTR = 0x31
TOKEN_UNICODE = 0x32
TOKEN_CSTRING = 0x33
TOKEN_ARRAY = 0x34


class ImportDirectXXFile(bpy.types.Operator, ImportHelper):
    bl_idname = "import_model.directx_x"
    bl_description = 'Import from X file (.x)'
    bl_label = "Import DirectX X File"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_options = {'UNDO'}

    filepath: StringProperty(
        name="input file",
        subtype='FILE_PATH'
    )

    filename_ext = ".x"

    filter_glob: StringProperty(
        default="*.x",
        options={'HIDDEN'},
    )

    remove_all: BoolProperty(
        name="Remove All Objects and Materials",
        default=True,
    )

    scale: FloatProperty(
        name="Scale",
        default=1.0
    )

    def __init__(self):
        self.mesh_vertexes = []
        self.mesh_faces = []
        self.mesh_vertexes_redirect = {}
        self.vertexes = []
        self.mesh_faces_exact = []
        self.mesh_tex_coord = []
        self.material_face_indexes = []
        self.material_count = 0
        self.materials = []
        self.is_binary = False
        self.float_size = 32
        self.ret_string = ""
        self.ret_integer = 0
        self.ret_float = 0
        self.ret_integer_list = []
        self.ret_float_list = []
        self.ret_uuid = ""
        self.byte_buffer = ByteBuffer(bytes())

    def parse_mesh(self, element):
        data = element.data
        size = int(data[0:data.find(";")].replace(" ", ""))
        num_matcher = NumMatcher(True, True)
        data = data[data.find(";") + 1:]
        num_matcher.set_target(data)
        vertex = [0.0, 0.0, 0.0]
        i = 0
        self.mesh_vertexes = []
        self.mesh_vertexes_redirect = {}
        vertex_index = 0
        while num_matcher.find():
            vertex[i] = float(num_matcher.group())
            i += 1
            if i == 3:
                i = 0
                # DirectX X Y Z
                # Blender X Z Y
                vector = (vertex[0] * self.scale, vertex[2] * self.scale, vertex[1] * self.scale)
                # 重複した座標は1つにまとめる
                # リダイレクト先を登録しておく
                if vector in self.mesh_vertexes:
                    self.mesh_vertexes_redirect[vertex_index] = self.mesh_vertexes.index(vector)
                else:
                    self.mesh_vertexes_redirect[vertex_index] = len(self.mesh_vertexes)
                    self.mesh_vertexes.append(vector)
                vertex_index += 1
                if vertex_index == size:
                    break
        data = data[num_matcher.get_end() + 1:]
        indexes_size = 0
        size = 0
        positive_num_matcher = NumMatcher(False, True)
        positive_num_matcher.set_target(data)
        indexes = []
        i = -2
        self.mesh_faces = []
        self.vertexes = []
        self.mesh_faces_exact = []
        while positive_num_matcher.find():
            if i == -2:
                indexes_size = int(positive_num_matcher.group())
            elif i == -1:
                size = int(positive_num_matcher.group())
                indexes = [0] * size
            else:
                indexes[i] = int(positive_num_matcher.group())
            i += 1
            if i == size:
                i = -1
                # Blenderに記録する際に使用する頂点のインデックス
                indexes.reverse()
                vertexes = []
                for l in range(len(indexes)):
                    if indexes[l] in self.mesh_vertexes_redirect:
                        vertexes.append(self.mesh_vertexes_redirect[indexes[l]])
                    else:
                        vertexes.append(indexes[l])
                self.mesh_faces.append(vertexes)
                # Xファイルに記述された実際の使用する頂点のインデックス(UV登録時に使用)
                self.mesh_faces_exact.append(indexes)
                if len(self.mesh_faces) == indexes_size:
                    break

    def parse_texture_coords(self, element):
        data = element.data
        num_matcher = NumMatcher(True, True)
        num_matcher.set_target(data)
        num_matcher.find()
        size = int(num_matcher.group())
        vertex = [0.0, 0.0]
        i = 0
        while num_matcher.find():
            vertex[i] = float(num_matcher.group())
            i += 1
            if i == 2:
                i = 0
                vertex[1] = -vertex[1] + 1
                self.mesh_tex_coord.append(vertex)
                vertex = [0.0, 0.0]
                if len(self.mesh_tex_coord) == size:
                    break

    def parse_mesh_material_list(self, element):
        data = element.data.replace(" ", "")
        num_matcher = NumMatcher(False, True)
        num_matcher.set_target(data)
        num_matcher.find()
        self.material_count = int(num_matcher.group())
        num_matcher.find()
        size = int(num_matcher.group())
        while num_matcher.find():
            self.material_face_indexes.append(int(num_matcher.group()))

    def parse_material(self, element):
        color = element.data[0:element.data.find(";;")].replace(" ", "").split(";")
        d = element.data[element.data.find(";;") + 2:]
        power = float(d[0:d.find(";")])
        d = d[d.find(";") + 1:]
        specular_color = d[0:d.find(";;")].split(";")
        d = d[d.find(";;") + 2:]
        emission_color = d[0:d.find(";;")].split(";")
        face_color = [1.0, 1.0, 1.0, 1.0]
        for i in range(len(color)):
            face_color[i] = float(color[i])
        material = XMaterial()
        material.face_color = face_color
        material.power = power
        material.specular_color = (
            float(specular_color[0]),
            float(specular_color[1]),
            float(specular_color[2])
        )
        material.emission_color = (
            float(emission_color[0]),
            float(emission_color[1]),
            float(emission_color[2]),
            1.0
        )
        material.name = element.name
        for tex in element.children:
            if tex.element_type == "TextureFilename":
                material.texture_path = tex.data[tex.data.find("\"") + 1:tex.data.rfind("\"")]
        self.materials.append(material)

    def parse_token(self):
        token = self.byte_buffer.get_short()
        if token == TOKEN_NAME:
            length = self.byte_buffer.get_int()
            self.ret_string = self.byte_buffer.get_length(length).decode()
        elif token == TOKEN_INTEGER:
            self.ret_integer = self.byte_buffer.get_int()
        elif token == TOKEN_STRING:
            length = self.byte_buffer.get_int()
            self.ret_string = self.byte_buffer.get_length(length).decode()
            self.parse_token()
        elif token == TOKEN_GUID:
            # GUIDは使用しないため無視する
            self.byte_buffer.get_int()
            self.byte_buffer.get_short()
            self.byte_buffer.get_short()
            self.byte_buffer.get_length(8)
        elif token == TOKEN_INTEGER_LIST:
            length = self.byte_buffer.get_int()
            self.ret_integer_list = [0] * length
            for i in range(length):
                self.ret_integer_list[i] = self.byte_buffer.get_int()
        elif token == TOKEN_FLOAT_LIST:
            length = self.byte_buffer.get_int()
            self.ret_float_list = [0.0] * length
            if self.float_size == 64:
                for i in range(length):
                    self.ret_float_list[i] = self.byte_buffer.get_double()
            else:
                for i in range(length):
                    self.ret_float_list[i] = self.byte_buffer.get_float()
        elif token == TOKEN_TEMPLATE:
            # テンプレートは使用する必要がないため無視する
            self.parse_token_loop(TOKEN_CBRACE)
        return token

    def parse_token_loop(self, token):
        while self.parse_token() != token:
            pass

    def parse_bin(self):
        self.materials = []
        while self.byte_buffer.has_remaining():
            token = self.parse_token()
            if token == TOKEN_NAME:
                if self.ret_string == "Mesh":
                    self.parse_mesh_bin()
                elif self.ret_string == "MeshTextureCoords":
                    self.parse_mesh_texture_coords_bin()
                elif self.ret_string == "MeshMaterialList":
                    self.parse_mesh_material_list_bin()

    def parse_mesh_bin(self):
        self.parse_token_loop(TOKEN_INTEGER_LIST)
        self.parse_token_loop(TOKEN_FLOAT_LIST)
        self.mesh_vertexes = []
        i = 0
        vertex_index = 0
        while vertex_index < self.ret_integer_list[0]:
            # DirectX X Y Z
            # Blender X Z Y
            vector = (
                self.ret_float_list[i] * self.scale,
                self.ret_float_list[i + 2] * self.scale,
                self.ret_float_list[i + 1] * self.scale
            )
            # 重複した座標は1つにまとめる
            # リダイレクト先を登録しておく
            if vector in self.mesh_vertexes:
                self.mesh_vertexes_redirect[vertex_index] = self.mesh_vertexes.index(vector)
            else:
                self.mesh_vertexes_redirect[vertex_index] = len(self.mesh_vertexes)
                self.mesh_vertexes.append(vector)
            vertex_index += 1
            i += 3
        self.parse_token_loop(TOKEN_INTEGER_LIST)
        self.mesh_faces = []
        i = 1
        while i < len(self.ret_integer_list):
            length = self.ret_integer_list[i]
            indexes = self.ret_integer_list[i + 1:i + 1 + length]
            # Blenderに記録する際に使用する頂点のインデックス
            indexes.reverse()
            vertexes = []
            for l in range(len(indexes)):
                if indexes[l] in self.mesh_vertexes_redirect:
                    vertexes.append(self.mesh_vertexes_redirect[indexes[l]])
                else:
                    vertexes.append(indexes[l])
            self.mesh_faces.append(vertexes)
            # Xファイルに記述された実際の使用する頂点のインデックス(UV登録時に使用)
            self.mesh_faces_exact.append(indexes)
            i += length + 1

    def parse_mesh_texture_coords_bin(self):
        self.parse_token_loop(TOKEN_INTEGER_LIST)
        self.parse_token_loop(TOKEN_FLOAT_LIST)
        self.mesh_tex_coord = []
        i = 0
        while i < len(self.ret_float_list):
            vertex = [self.ret_float_list[i], self.ret_float_list[i + 1]]
            vertex[1] = -vertex[1] + 1
            self.mesh_tex_coord.append(vertex)
            i += 2

    def parse_mesh_material_list_bin(self):
        self.parse_token_loop(TOKEN_INTEGER_LIST)
        self.material_count = self.ret_integer_list[0]
        i = 2
        self.material_face_indexes = self.ret_integer_list[2:self.ret_integer_list[1] + 2]
        pos = self.byte_buffer.pos
        while True:
            token = self.parse_token()
            if token == TOKEN_NAME and self.ret_string == "Material":
                self.parse_material_bin()
            else:
                self.byte_buffer.pos = pos
                break
            pos = self.byte_buffer.pos

    def parse_material_bin(self):
        token = self.parse_token()
        material_name = ""
        if token == TOKEN_NAME:
            material_name = self.ret_string
        self.parse_token_loop(TOKEN_FLOAT_LIST)
        material = XMaterial()
        material.name = material_name
        material.face_color = self.ret_float_list[0:4]
        material.power = self.ret_float_list[4]
        material.specular_color = self.ret_float_list[5:8]
        material.emission_color = (self.ret_float_list[8], self.ret_float_list[9], self.ret_float_list[10], 1.0)
        token = self.parse_token()
        if token == TOKEN_NAME and self.ret_string == "TextureFilename":
            self.parse_token_loop(TOKEN_STRING)
            material.texture_path = self.ret_string
            self.parse_token_loop(TOKEN_CBRACE)
        if token != TOKEN_CBRACE:
            self.parse_token_loop(TOKEN_CBRACE)
        self.materials.append(material)

    def execute(self, context):
        for obj in bpy.context.scene.objects:
            obj.select_set(False)

        if self.remove_all:
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    obj.select_set(True)
                else:
                    obj.select_set(False)
            bpy.ops.object.delete()
            for material in bpy.data.materials:
                material.user_clear()
                bpy.data.materials.remove(material)

        # xファイルを読み込み
        with open(self.filepath, "rb") as f:
            header = f.read(16)
            if header[0:4] == b'xof ':
                # フォーマットのチェック
                if header[8:12] == b'txt ':
                    self.is_binary = False
                elif header[8:12] == b'bin ':
                    self.is_binary = True
            else:
                raise Exception(bpy.app.translations.pgettext("This file is not X file!"))

        if self.is_binary:
            # バイナリ
            with open(self.filepath, "rb") as f:
                f.read(16)
                data = f.read()
                self.byte_buffer = ByteBuffer(data)
                self.parse_bin()
        else:
            # テキスト
            with open(self.filepath) as f:
                x_model_file_string = f.read().split("\n")
                x_elements = []
                x_element = XElement()

                # テキストデータからXElementにパース
                for line in range(len(x_model_file_string)):
                    if line <= x_element.end_line_num:
                        continue
                    x_element = to_XElement(x_model_file_string, line)
                    x_elements.append(x_element)

                # XElementからデータを分析
                for element in x_elements:
                    if element.element_type == "Mesh":
                        self.parse_mesh(element)

                        for ele in element.children:
                            # テクスチャの座標(UV)
                            if ele.element_type == "MeshTextureCoords":
                                self.parse_texture_coords(ele)
                            # マテリアルのリスト マテリアル数;\n面の数;\nその面が使用するマテリアルのインデックス,...
                            if ele.element_type == "MeshMaterialList":
                                self.parse_mesh_material_list(ele)
                                for ch in ele.children:
                                    if ch.element_type == "Material":
                                        self.parse_material(ch)
                    else:
                        if element.element_type == "Material":
                            self.parse_material(element)
                        elif element.element_type == "MeshTextureCoords":
                            self.parse_texture_coords(element)
        material_faces = []
        for i in range(self.material_count):
            material_faces.append([])

        # マテリアル別に面を整理
        if self.material_count > 0:
            for i in range(len(self.mesh_faces)):
                if len(self.material_face_indexes) <= i:
                    self.material_face_indexes.append(0)
                material_id = self.material_face_indexes[i]
                material_faces[material_id].append(i)

        # モデル名を決定
        model_name = os.path.splitext(os.path.basename(self.filepath))[0]

        # マテリアルごとにオブジェクトを作成
        for j in range(len(material_faces)):
            faces_data = []
            vertexes_data = []
            faces = material_faces[j]
            if len(faces) == 0:
                continue
            # マテリアルの有無
            available_material = len(self.materials) > self.material_face_indexes[faces[0]]
            x_material = self.materials[self.material_face_indexes[faces[0]]]
            # マテリアルを作成
            material_name = model_name + "Material"
            if x_material.name:
                material_name = x_material.name
            material = bpy.data.materials.new(material_name)

            # ブレンドモードの設定
            material.blend_method = 'CLIP'
            material.shadow_method = 'CLIP'

            # ノードを有効化
            material.use_nodes = True
            nodes = material.node_tree.nodes
            # プリンシプルBSDFを取得
            principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')

            color = (1.0, 1.0, 1.0)
            material.specular_intensity = 0.0
            if available_material:
                color = x_material.face_color
                material.specular_intensity = x_material.power
                material.specular_color = x_material.specular_color
                principled.inputs['Base Color'].default_value = color
                principled.inputs['Alpha'].default_value = x_material.face_color[3]
            material.diffuse_color = color

            # 鏡面反射
            principled.inputs['Specular'].default_value = 0.0
            # 放射を設定
            principled.inputs['Emission'].default_value = x_material.emission_color

            # テクスチャの紐付け
            if x_material.texture_path and x_material.texture_path != "":
                path = "/".join(os.path.abspath(self.filepath).split(os.path.sep)[0:-1])
                path = path + "/" + x_material.texture_path
                if os.path.exists(path):
                    x_material.texture_path = path

            if x_material.texture_path != "":
                # 画像ノードを作成
                texture = material.node_tree.nodes.new("ShaderNodeTexImage")
                texture.location = (-300, 150)

                # 画像を読み込み
                texture.image = bpy.data.images.load(filepath=x_material.texture_path)
                texture.image.colorspace_settings.name = 'Non-Color'
                # ベースカラーとテクスチャのカラーをリンクさせる
                material.node_tree.links.new(principled.inputs['Base Color'], texture.outputs['Color'])
                # アルファとテクスチャのアルファをリンクさせる
                material.node_tree.links.new(principled.inputs['Alpha'], texture.outputs['Alpha'])

            # 頂点データと面データを作成
            # マテリアルが使う頂点だけを抽出、その頂点のインデックスに合わせて面の頂点のインデックスを変更
            mesh_indexes = {}
            for i in faces:
                face = self.mesh_faces[i]
                # faces_data.append(face)
                for k in face:
                    if self.mesh_vertexes[k] in vertexes_data:
                        mesh_indexes[k] = vertexes_data.index(self.mesh_vertexes[k])
                    else:
                        mesh_indexes[k] = len(vertexes_data)
                        vertexes_data.append(self.mesh_vertexes[k])
                count = 0
                face_data = [0] * len(face)
                for k in face:
                    face_data[count] = mesh_indexes[k]
                    count += 1
                faces_data.append(face_data)

            # メッシュを作成
            mesh = bpy.data.meshes.new("mesh")

            # メッシュに頂点と面のデータを挿入
            mesh.from_pydata(vertexes_data, [], faces_data)

            # UVレイヤーの作成
            mesh.uv_layers.new(name="UVMap")
            uv = mesh.uv_layers["UVMap"]

            # UVデータを頂点と紐付ける
            count = 0
            for i in faces:
                for k in self.mesh_faces_exact[i]:
                    uv.data[count].uv = self.mesh_tex_coord[k]
                    count += 1

            mesh.update()

            # メッシュでオブジェクトを作成
            obj = bpy.data.objects.new(model_name, mesh)
            obj.data = mesh
            obj.data.materials.append(material)

            # オブジェクトをシーンに追加
            scene = bpy.context.scene
            scene.collection.objects.link(obj)
            obj.select_set(True)
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
            obj.select_set(False)

        return {'FINISHED'}


# Xファイルに出力
class ExportDirectXXFile(bpy.types.Operator, ExportHelper):
    bl_idname = "export_model.directx_x"
    bl_description = 'Export to X file (.x)'
    bl_label = "Export DirectX X File"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_options = {'UNDO'}

    filepath: StringProperty(
        name="export file",
        subtype='FILE_PATH'
    )

    filename_ext = ".x"

    filter_glob: StringProperty(
        default="*.x",
        options={'HIDDEN'},
    )

    scale: FloatProperty(
        name="Scale",
        default=1.0,
    )

    mode: EnumProperty(
        items=[
            ("text", "Text", "Text mode"),
            ("binary", "Binary", "Binary mode"),
        ],
        name="Output mode"
    )

    export_material_name: BoolProperty(
        name="Export material name",
        default=True,
    )

    export_selected_only: BoolProperty(
        name="Export only selected objects",
        default=False,
    )

    def execute(self, context):
        if not self.filepath.endswith(".x"):
            return {'CANCELLED'}

        vertexes = []
        vertexes_dict = {}
        normals = []
        normals_dict = {}
        vertex_use_normal = []
        faces = []
        materials_dict = {}
        materials = []
        x_materials = []
        faces_use_material = []
        uv_data = []
        fake_material = gen_fake_material()

        is_binary = False
        if self.mode == "binary":
            is_binary = True

        target_objects = bpy.context.scene.objects
        if self.export_selected_only:
            target_objects = bpy.context.selected_objects
        for obj in target_objects:
            if obj.type == 'MESH' and not obj.hide_get():
                # モディファイヤーを適用した状態のオブジェクトを取得
                # obj_tmp = obj.copy()
                obj_tmp = obj.evaluated_get(context.evaluated_depsgraph_get())
                mesh: bpy.types.Mesh = obj_tmp.data
                # もとのオブジェクトに影響を与えないためコピー
                mesh = mesh.copy()
                # オブジェクトモードでの操作を適用した状態のメッシュを取得
                mesh.transform(obj.matrix_world)
                uv_vertexes = mesh.uv_layers[0].data
                vertex_index = 0
                for polygon in mesh.polygons:
                    ver = []
                    normal = []
                    smooth_shading = polygon.use_smooth
                    nor = polygon.normal
                    vertex_index += len(polygon.vertices) - 1
                    texture = ""
                    if len(mesh.materials) == 0:
                        if fake_material.name not in materials_dict.keys():
                            materials_dict[fake_material.name] = len(materials_dict.keys())
                            materials.append(fake_material)
                        faces_use_material.append(materials_dict[fake_material.name])
                    else:
                        for material in mesh.materials:
                            if material.name not in materials_dict.keys():
                                materials_dict[material.name] = len(materials_dict.keys())
                                materials.append(material)
                            if material.use_nodes:
                                # ノードを取得
                                nodes = material.node_tree.nodes
                                # プリンシプルBSDFを取得
                                principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
                                # テクスチャの有無を確認
                                if len(principled.inputs['Base Color'].links) > 0:
                                    for link in principled.inputs['Base Color'].links:
                                        if link.from_node.type == "TEX_IMAGE":
                                            texture = os.path.basename(link.from_node.image.filepath)
                        faces_use_material.append(materials_dict[mesh.materials[polygon.material_index].name])

                    for vertex in reversed(polygon.vertices):
                        vertex_co = mesh.vertices[vertex].co
                        # スケールに合わせる
                        vertex_co[0] *= self.scale
                        vertex_co[1] *= self.scale
                        vertex_co[2] *= self.scale
                        # 頂点が他のデータと重複していたらそれを使用する
                        # 頂点とUVはセットなのでセットで重複を調べる
                        uv = uv_vertexes[vertex_index].uv
                        if texture == "":
                            uv = (0.0, 0.0)
                        key = vertex_to_str(vertex_co) + str(uv)
                        if key not in vertexes_dict.keys():
                            vertexes_dict[key] = len(vertexes_dict.keys())
                            vertexes.append(vertex_co)
                            uv_data.append(uv)
                        if smooth_shading:
                            nor = mesh.vertices[vertex].normal
                        if vertex_to_str(nor) not in normals_dict.keys():
                            normals_dict[vertex_to_str(nor)] = len(normals_dict.keys())
                            normals.append(nor)
                        ver.append(vertexes_dict[key])
                        normal.append(normals_dict[vertex_to_str(nor)])
                        vertex_index -= 1
                    vertex_index += len(polygon.vertices) + 1
                    faces.append(ver)
                    vertex_use_normal.append(normal)

        for material in materials:
            # ノードを使用するかどうか
            x_material = XMaterial()
            # マテリアル名はアルファベット英数字、アンダーバー、ハイフン
            if re.fullmatch("[0-9A-z_-]*", material.name):
                x_material.name = material.name
            if material.use_nodes:
                texture = ""

                # ノードを取得
                nodes = material.node_tree.nodes
                # プリンシプルBSDFを取得
                principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
                # ベースカラー
                if len(principled.inputs['Base Color'].links) > 0:
                    need_color = True
                    for link in principled.inputs['Base Color'].links:
                        if link.from_node.type == "TEX_IMAGE":
                            texture = os.path.basename(link.from_node.image.filepath)
                        if link.from_node.type == "RGB":
                            need_color = False
                            for out in link.from_node.outputs:
                                if out.type == 'RGBA':
                                    x_material.face_color = out.default_value
                    if need_color:
                        x_material.face_color = (1.0, 1.0, 1.0, 1.0)
                else:
                    x_material.face_color = principled.inputs['Base Color'].default_value
                # 鏡面反射
                x_material.power = 0.0
                x_material.specular_color = (0.0, 0.0, 0.0)

                # 放射色
                x_material.emission_color = principled.inputs['Emission'].default_value

                if texture != "":
                    x_material.texture_path = texture
            else:
                # ベースカラー
                x_material.face_color = material.diffuse_color
                # 鏡面反射
                x_material.power = material.specular_intensity
                # 鏡面反射色
                x_material.specular_color = material.specular_color
                # 放射色
                x_material.emission_color = (0.0, 0.0, 0.0)
            x_materials.append(x_material)

        if is_binary:
            with open(self.filepath, mode='wb') as f:
                f.write(b'xof 0302bin 0032')
                # テンプレート
                write_shorts(f, [TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "Vector")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0x3D82AB5E, 0x62DA, 0x11CF, b'\xAB\x39\x00\x20\xAF\x71\xE4\x33')
                write_shorts(f, [TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "x")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "y")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "z")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "MeshFace")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0x3D82AB5F, 0x62DA, 0x11CF, b'\xAB\x39\x00\x20\xAF\x71\xE4\x33')
                write_shorts(f, [TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nFaceVertexIndices")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_ARRAY, TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "faceVertexIndices")
                write_shorts(f, [TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "nFaceVertexIndices")
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_SEMICOLON, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "Mesh")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0x3D82AB44, 0x62DA, 0x11CF, b'\xAB\x39\x00\x20\xAF\x71\xE4\x33')
                write_shorts(f, [TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nVertices")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_ARRAY, TOKEN_NAME])
                write_str(f, "Vector")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "vertices")
                write_shorts(f, [TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "nVertices")
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_SEMICOLON, TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nFaces")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_ARRAY, TOKEN_NAME])
                write_str(f, "MeshFace")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "faces")
                write_shorts(f, [TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "nFaces")
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_SEMICOLON, TOKEN_OBRACKET, TOKEN_DOT, TOKEN_DOT, TOKEN_DOT,
                                 TOKEN_CBRACKET, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "MeshNormals")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0xF6F23F43, 0x7686, 0x11CF, b'\x8F\x52\x00\x40\x33\x35\x94\xA3')
                write_shorts(f, [TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nNormals")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_ARRAY, TOKEN_NAME])
                write_str(f, "Vector")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "normals")
                write_shorts(f, [TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "nNormals")
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_SEMICOLON, TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nFaceNormals")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_ARRAY, TOKEN_NAME])
                write_str(f, "MeshFace")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "faceNormals")
                write_shorts(f, [TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "nFaceNormals")
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_SEMICOLON, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "Coords2d")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0xF6F23F44, 0x7686, 0x11CF, b'\x8F\x52\x00\x40\x33\x35\x94\xA3')
                write_shorts(f, [TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "u")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "v")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "MeshTextureCoords")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0xF6F23F40, 0x7686, 0x11CF, b'\x8F\x52\x00\x40\x33\x35\x94\xA3')
                write_shorts(f, [TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nTextureCoords")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_ARRAY, TOKEN_NAME])
                write_str(f, "Coords2d")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "textureCoords")
                write_shorts(f, [TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "nTextureCoords")
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_SEMICOLON, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "ColorRGBA")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0x35FF44E0, 0x6C7C, 0x11CF, b'\x8F\x52\x00\x40\x33\x35\x94\xA3')
                write_shorts(f, [TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "red")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "green")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "blue")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "alpha")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "ColorRGB")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0xD3E16E81, 0x7835, 0x11CF, b'\x8F\x52\x00\x40\x33\x35\x94\xA3')
                write_shorts(f, [TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "red")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "green")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "blue")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "Material")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0x3D82AB4D, 0x62DA, 0x11CF, b'\xAB\x39\x00\x20\xAF\x71\xE4\x33')
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "ColorRGBA")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "faceColor")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_FLOAT, TOKEN_NAME])
                write_str(f, "power")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_NAME])
                write_str(f, "ColorRGB")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "specularColor")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_NAME])
                write_str(f, "ColorRGB")
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "emissiveColor")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_OBRACKET, TOKEN_DOT, TOKEN_DOT, TOKEN_DOT,
                                 TOKEN_CBRACKET, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "MeshMaterialList")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0xF6F23F42, 0x7686, 0x11CF, b'\x8F\x52\x00\x40\x33\x35\x94\xA3')
                write_shorts(f, [TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nMaterials")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "nFaceIndexes")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_ARRAY, TOKEN_DWORD, TOKEN_NAME])
                write_str(f, "faceIndexes")
                write_shorts(f, [TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "nFaceIndexes")
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_SEMICOLON, TOKEN_OBRACKET, TOKEN_NAME])
                write_str(f, "Material")
                write_shorts(f, [TOKEN_GUID])
                write_guid(f, 0x3D82AB4D, 0x62DA, 0x11CF, b'\xAB\x39\x00\x20\xAF\x71\xE4\x33')
                write_shorts(f, [TOKEN_CBRACKET, TOKEN_CBRACE, TOKEN_TEMPLATE, TOKEN_NAME])
                write_str(f, "TextureFilename")
                write_shorts(f, [TOKEN_OBRACE, TOKEN_GUID])
                write_guid(f, 0xA42790E1, 0x7810, 0x11CF, b'\x8F\x52\x00\x40\x33\x35\x94\xA3')
                write_shorts(f, [TOKEN_LPSTR, TOKEN_NAME])
                write_str(f, "filename")
                write_shorts(f, [TOKEN_SEMICOLON, TOKEN_CBRACE])
                # メッシュ
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "Mesh")
                write_shorts(f, [TOKEN_OBRACE])
                write_integer_list(f, [len(vertexes)])
                vertex_list = []
                for vertex in vertexes:
                    vertex_list.append(vertex[0])
                    vertex_list.append(vertex[2])
                    vertex_list.append(vertex[1])
                write_float_list(f, vertex_list)
                faces_list = [len(faces)]
                for face in faces:
                    faces_list.append(len(face))
                    for i in face:
                        faces_list.append(i)
                write_integer_list(f, faces_list)
                write_shorts(f, [TOKEN_NAME])
                write_str(f, "MeshNormals")
                write_shorts(f, [TOKEN_OBRACE])
                write_integer_list(f, [len(normals)])
                vertex_list = []
                for vertex in normals:
                    vertex_list.append(vertex[0])
                    vertex_list.append(vertex[2])
                    vertex_list.append(vertex[1])
                write_float_list(f, vertex_list)
                faces_list = [len(vertex_use_normal)]
                for face in vertex_use_normal:
                    faces_list.append(len(face))
                    for i in face:
                        faces_list.append(i)
                write_integer_list(f, faces_list)
                write_shorts(f, [TOKEN_CBRACE, TOKEN_NAME])
                write_str(f, "MeshTextureCoords")
                write_shorts(f, [TOKEN_OBRACE])
                write_integer_list(f, [len(uv_data)])
                vertex_list = []
                for uv in uv_data:
                    vertex_list.append(uv[0])
                    vertex_list.append(-uv[1] + 1)
                write_float_list(f, vertex_list)
                write_shorts(f, [TOKEN_CBRACE, TOKEN_NAME])
                write_str(f, "MeshMaterialList")
                write_shorts(f, [TOKEN_OBRACE])
                index_list = [len(x_materials), len(faces_use_material)]
                index_list[2:len(faces_use_material) + 2] = faces_use_material
                write_integer_list(f, index_list)
                for x_material in x_materials:
                    write_shorts(f, [TOKEN_NAME])
                    write_str(f, "Material")
                    if self.export_material_name and x_material.name:
                        write_shorts(f, [TOKEN_NAME])
                        write_str(f, x_material.name)
                    write_shorts(f, [TOKEN_OBRACE])
                    color_list = [0.0] * 11
                    color_list[0:4] = x_material.face_color[0:4]
                    color_list[4] = x_material.power
                    color_list[5:8] = x_material.specular_color[0:3]
                    color_list[8:11] = x_material.emission_color[0:3]
                    write_float_list(f, color_list)
                    if x_material.texture_path != "":
                        write_shorts(f, [TOKEN_NAME])
                        write_str(f, "TextureFilename")
                        write_shorts(f, [TOKEN_OBRACE, TOKEN_STRING])
                        write_str(f, x_material.texture_path)
                        write_shorts(f, [TOKEN_SEMICOLON, TOKEN_CBRACE])
                    write_shorts(f, [TOKEN_CBRACE])
                write_shorts(f, [TOKEN_CBRACE, TOKEN_CBRACE])
        else:
            x_file_content = '''xof 0302txt 0032

Header {
 1;
 0;
 1;
}

template Vector {
 <3d82ab5e-62da-11cf-ab39-0020af71e433>
 FLOAT x;
 FLOAT y;
 FLOAT z;
}

template MeshFace {
 <3d82ab5f-62da-11cf-ab39-0020af71e433>
 DWORD nFaceVertexIndices;
 array DWORD faceVertexIndices[nFaceVertexIndices];
}

template Mesh {
 <3d82ab44-62da-11cf-ab39-0020af71e433>
 DWORD nVertices;
 array Vector vertices[nVertices];
 DWORD nFaces;
 array MeshFace faces[nFaces];
 [...]
}

template MeshNormals {
 <f6f23f43-7686-11cf-8f52-0040333594a3>
 DWORD nNormals;
 array Vector normals[nNormals];
 DWORD nFaceNormals;
 array MeshFace faceNormals[nFaceNormals];
}

template Coords2d {
 <f6f23f44-7686-11cf-8f52-0040333594a3>
 FLOAT u;
 FLOAT v;
}

template MeshTextureCoords {
 <f6f23f40-7686-11cf-8f52-0040333594a3>
 DWORD nTextureCoords;
 array Coords2d textureCoords[nTextureCoords];
}

template ColorRGBA {
 <35ff44e0-6c7c-11cf-8f52-0040333594a3>
 FLOAT red;
 FLOAT green;
 FLOAT blue;
 FLOAT alpha;
}

template ColorRGB {
 <d3e16e81-7835-11cf-8f52-0040333594a3>
 FLOAT red;
 FLOAT green;
 FLOAT blue;
}

template Material {
 <3d82ab4d-62da-11cf-ab39-0020af71e433>
 ColorRGBA faceColor;
 FLOAT power;
 ColorRGB specularColor;
 ColorRGB emissiveColor;
 [...]
}

template MeshMaterialList {
 <f6f23f42-7686-11cf-8f52-0040333594a3>
 DWORD nMaterials;
 DWORD nFaceIndexes;
 array DWORD faceIndexes[nFaceIndexes];
 [Material <3d82ab4d-62da-11cf-ab39-0020af71e433>]
}

template TextureFilename {
 <a42790e1-7810-11cf-8f52-0040333594a3>
 STRING filename;
}

'''

            x_file_content += "Mesh {\n"
            x_file_content += " " + str(len(vertexes)) + ";\n"

            # 頂点データ
            for vertex in vertexes:
                x_file_content += " " + vertex_to_str(vertex) + ";,\n"
            x_file_content = x_file_content[0:-2] + ";\n"

            # 面データ
            x_file_content += " " + str(len(faces)) + ";\n"
            for face in faces:
                x_file_content += " " + str(len(face)) + ";" + str(face).replace(" ", "")[1:-1] + ";,\n"
            x_file_content = x_file_content[0:-2] + ";\n\n"

            # マテリアルデータ
            x_file_content += " MeshMaterialList {\n"
            x_file_content += "  " + str(len(materials)) + ";\n"
            x_file_content += "  " + str(len(faces_use_material)) + ";\n"
            for material_index in faces_use_material:
                x_file_content += "  " + str(material_index) + ",\n"
            x_file_content = x_file_content[0:-2] + ";\n\n"

            for x_material in x_materials:
                if self.export_material_name and x_material.name:
                    x_file_content += "  Material " + x_material.name + " {\n"
                else:
                    x_file_content += "  Material {\n"
                x_file_content += "   " + \
                                  float_to_str(round(x_material.face_color[0], 6)) + ";" + \
                                  float_to_str(round(x_material.face_color[1], 6)) + ";" + \
                                  float_to_str(round(x_material.face_color[2], 6)) + ";" + \
                                  float_to_str(round(x_material.face_color[3], 6)) + ";;\n"
                x_file_content += "   " + float_to_str(round(x_material.power, 6)) + ";\n"
                x_file_content += "   " + \
                                  float_to_str(round(x_material.specular_color[0], 6)) + ";" + \
                                  float_to_str(round(x_material.specular_color[1], 6)) + ";" + \
                                  float_to_str(round(x_material.specular_color[2], 6)) + ";;\n"
                x_file_content += "   " + \
                                  float_to_str(round(x_material.emission_color[0], 6)) + ";" + \
                                  float_to_str(round(x_material.emission_color[1], 6)) + ";" + \
                                  float_to_str(round(x_material.emission_color[2], 6)) + ";;\n"
                if x_material.texture_path != "":
                    x_file_content += "\n   TextureFilename {\n"
                    x_file_content += "    \"" + x_material.texture_path + "\";\n"
                    x_file_content += "   }\n"
                x_file_content += "  }\n\n"
            x_file_content = x_file_content[0:-1]
            x_file_content += " }\n\n"

            # 法線データ
            x_file_content += " MeshNormals {\n"
            x_file_content += "  " + str(len(normals)) + ";\n"
            for normal in normals:
                x_file_content += "  " + vertex_to_str(normal) + ";,\n"
            x_file_content = x_file_content[0:-2] + ";\n"
            x_file_content += "  " + str(len(vertex_use_normal)) + ";\n"
            for vertex in vertex_use_normal:
                x_file_content += "  " + str(len(vertex)) + ";" + str(vertex).replace(" ", "")[1:-1] + ";,\n"
            x_file_content = x_file_content[0:-2] + ";\n"
            x_file_content += " }\n\n"

            # UVデータ
            x_file_content += " MeshTextureCoords {\n"
            x_file_content += "  " + str(len(uv_data)) + ";\n"
            for vertex in uv_data:
                x_file_content += "  " + float_to_str(round(vertex[0], 6)) + ";" + float_to_str(round(-vertex[1] + 1, 6)) + ";,\n"
            x_file_content = x_file_content[0:-2] + ";\n"
            x_file_content += " }\n"
            x_file_content += "}\n"

            with open(self.filepath, mode='w') as f:
                f.write(x_file_content)

        # 生成した偽物のマテリアルを削除
        fake_material.user_clear()
        bpy.data.materials.remove(fake_material)

        return {'FINISHED'}


def menu_func_import(self, context):
    if bpy.context.mode != "OBJECT":
        return
    self.layout.operator(ImportDirectXXFile.bl_idname, text="DirectX XFile (.x)")


def menu_func_export(self, context):
    if bpy.context.mode != "OBJECT":
        return
    self.layout.operator(ExportDirectXXFile.bl_idname, text="DirectX XFile (.x)")

class UpdatedDialog(Operator):
    bl_idname = "xfilesupport.updated"
    bl_label = "XFileSupport Updated"

    version: bpy.props.StringProperty(name="Updated version")

    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="XFileSupport was updated to " + self.version + ".")
        col.label(text="Please restart blender to apply this update.")

def invoke_updated_dialog(updated_version):
    bpy.ops.xfilesupport.updated('INVOKE_DEFAULT', version=updated_version)

def show_updated_dialog(version):
    bpy.app.timers.register(functools.partial(invoke_updated_dialog, version), first_interval=.01)

def check_update():
    try:
        req = urllib.request.Request(
            'https://raw.githubusercontent.com/kusaanko/Blender_XFileSupport_BVE/main/versions.json'
        )
        with urllib.request.urlopen(req) as response:
            body = response.read()
            json_data = json.loads(body)
            for versions in json_data:
                if (versions['blender_major'], versions['blender_minor'], versions['blender_subversion']) \
                        <= bpy.app.version:
                    if (versions['version_major'], versions['version_minor'], versions['version_subversion']) \
                            > bl_info['version']:
                        # Update available
                        if "file_url" in versions and "file_name" in versions:
                            req = urllib.request.Request(
                                versions['file_url']
                            )
                            with urllib.request.urlopen(req) as response:
                                body = response.read()
                                os.remove(bpy.utils.user_resource('SCRIPTS', path="addons") + "\\" + os.path.basename(__file__))
                                f = open(bpy.utils.user_resource('SCRIPTS', path="addons") + "\\" + versions['file_name'], 'bw')
                                f.write(body)
                                print("Updated XFileSupport to " + str(versions['version_major']) + "." + str(versions['version_minor']) + "." + str(versions['version_subversion']))
                                print("  to " + bpy.utils.user_resource('SCRIPTS', path="addons") + "\\" + versions['file_name'])
                                # Show updated dialog
                                show_updated_dialog(str(versions['version_major']) + "." + str(versions['version_minor']) + "." + str(versions['version_subversion']))
                        else:
                            html = """
<html>
<head>
  <title>XFileSupport Update</title>
  <meta charset="UTF-8" />
</head>
<body>
  <h1>""" + bpy.app.translations.pgettext("The update of XFileSupport is available!") + """</h1>
  <p>""" + bpy.app.translations.pgettext("Your version:") + " " + str(bl_info['version'][0]) + "." + str(
                            bl_info['version'][1]) + "." + str(bl_info['version'][2]) + """</p>
  <p>""" + bpy.app.translations.pgettext("New version:") + " " + str(versions['version_major']) + "." + str(
                            versions['version_minor']) + "." + str(versions['version_subversion']) + """</p>
  <p><a href=""" + versions['download_link'] + ">" + bpy.app.translations.pgettext("Please download from this link.") + """</a></p>
</body>
</html>"""
                            webbrowser.open_new_tab(
                                "https://kusaanko.github.io/custom_page.html?" + urllib.parse.quote(html))
                            break
    except OSError as e:
        print(e)

def register():
    bpy.utils.register_class(ImportDirectXXFile)
    bpy.utils.register_class(ExportDirectXXFile)
    bpy.utils.register_class(UpdatedDialog)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    thread = threading.Thread(target=check_update)
    thread.start()

    bpy.app.translations.register(__name__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__name__)

    bpy.utils.unregister_class(ImportDirectXXFile)
    bpy.utils.unregister_class(ExportDirectXXFile)
    bpy.utils.unregister_class(UpdatedDialog)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()


def to_XElement(x_model_file_string, start_line_num):
    element_type = ""
    elem_data = ""
    end_index = 0
    children = []
    skip = 0
    element_name = ""
    for line_num in range(len(x_model_file_string))[start_line_num:]:
        if line_num <= skip:
            continue
        line = x_model_file_string[line_num]
        pos = line.find("{")
        if pos != -1 and "}" in line:
            continue

        if "{" in line:
            if element_type == "":
                element_type = re.sub('\t', "", line[0:line.index("{")])
                element_type = re.sub('^ *', "", element_type)
                if element_type.find(" ") != -1:
                    element_name = element_type[element_type.find(" ") + 1:]
                    element_type = element_type[0:element_type.find(" ")]
                    if re.search("[^ ]*", element_name):
                        element_name = re.search("[^ ]*", element_name).group(0)
                if element_type == "":
                    element_type = "empty"
            else:
                x_element = to_XElement(x_model_file_string, line_num)
                children.append(x_element)
                skip = x_element.end_line_num
        else:
            if "}" in line:
                end_index = line_num
                break
            else:
                if len(element_type) > 0:
                    elem_data += line.replace("\r", "")
    result = XElement()
    result.element_type = element_type
    result.data = elem_data
    result.children = children
    result.end_line_num = end_index
    result.name = element_name
    return result


def vertex_to_str(vertex):
    # Blender X Z Y
    # DirectX X Y Z
    return float_to_str(round(vertex[0], 6)) + ";" + float_to_str(round(vertex[2], 6)) + ";" + float_to_str(round(vertex[1], 6))


def gen_fake_material():
    # 偽物のマテリアルを作成
    material = bpy.data.materials.new("NoneMaterial")

    material.specular_intensity = 0.0
    material.specular_color = (0.0, 0.0, 0.0)
    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)

    # ブレンドモードの設定
    material.blend_method = 'CLIP'
    material.shadow_method = 'CLIP'

    # ノードを有効化
    material.use_nodes = True

    nodes = material.node_tree.nodes
    # プリンシプルBSDFを取得
    principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')

    # ベースカラーを設定
    principled.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)

    # スペキュラーを設定
    principled.inputs['Specular'].default_value = 0.0

    # 放射を設定
    principled.inputs['Emission'].default_value = (0.0, 0.0, 0.0, 1.0)
    return material


def float_to_str(f):
    float_string = repr(f)
    if 'e' in float_string:  # detect scientific notation
        digits, exp = float_string.split('e')
        digits = digits.replace('.', '').replace('-', '')
        exp = int(exp)
        zero_padding = '0' * (abs(int(exp)) - 1)  # minus 1 for decimal point in the sci notation
        sign = '-' if f < 0 else ''
        if exp > 0:
            float_string = '{}{}{}.0'.format(sign, digits, zero_padding)
        else:
            float_string = '{}0.{}{}'.format(sign, zero_padding, digits)
    length = len(float_string[float_string.find(".") + 1:])
    if length < 6:
        float_string = float_string + ("0" * (6 - length))
    return float_string


def write_int(f, i):
    f.write(i.to_bytes(4, byteorder='little'))


def write_short(f, i):
    f.write(i.to_bytes(2, byteorder='little'))


def write_float(f, i):
    f.write(struct.pack('<f', float(i)))


def write_shorts(f, shorts):
    for s in shorts:
        write_short(f, s)


def write_str(f, string):
    write_int(f, len(string))
    f.write(string.encode())


def write_guid(f, data1, data2, data3, data4):
    write_int(f, data1)
    write_shorts(f, [data2, data3])
    f.write(data4)


def write_integer_list(f, i_list):
    write_short(f, TOKEN_INTEGER_LIST)
    write_int(f, len(i_list))
    for i in i_list:
        write_int(f, i)


def write_float_list(f, f_list):
    write_short(f, TOKEN_FLOAT_LIST)
    write_int(f, len(f_list))
    for i in f_list:
        write_float(f, i)


class XElement:
    element_type = ""
    data = ""
    children = []
    end_line_num = 0
    name = ""


class XMaterial:
    face_color = ()
    power = 0.0
    specular_color = ()
    emission_color = ()
    texture_path = ""
    name = ""


class NumMatcher:

    def __init__(self, negative=True, decimal=True):
        self.negative = negative
        self.decimal = decimal
        self.target = []
        self.target_str = ""
        self.pos = 0
        self.start = 0
        self.end = 0

    def set_target(self, target):
        self.target = list(target)
        self.target_str = target
        self.pos = 0

    def find(self):
        start_num = False
        negative = False
        while self.pos < len(self.target):
            c = self.target[self.pos]
            if start_num:
                if not ((self.decimal and c == '.') or ('0' <= c <= '9')):
                    self.end = self.pos
                    if negative and self.end - self.start == 1:
                        start_num = False
                        negative = False
                    else:
                        return True
            else:
                if self.negative:
                    if c == '-':
                        start_num = True
                        negative = True
                        self.start = self.pos
                if '0' <= c <= '9':
                    start_num = True
                    self.start = self.pos
            self.pos += 1
        return False

    def get_start(self):
        return self.start

    def get_end(self):
        return self.end

    def group(self):
        return self.target_str[self.start:self.end]


class ByteBuffer:

    def __init__(self, data):
        self.array = bytearray(data)
        self.pos = 0

    def get(self):
        value = self.array[self.pos]
        self.pos += 1
        return value

    def get_length(self, length):
        value = self.array[self.pos:self.pos + length]
        self.pos += length
        return value

    def get_int(self):
        return int.from_bytes(self.get_length(4), byteorder='little')

    def get_short(self):
        return int.from_bytes(self.get_length(2), byteorder='little')

    def get_float(self):
        return struct.unpack("<f", self.get_length(4))[0]

    def get_double(self):
        return struct.unpack("<d", self.get_length(8))[0]

    def has_remaining(self):
        return len(self.array) > self.pos
