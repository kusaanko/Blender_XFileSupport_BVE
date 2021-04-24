# https://github.com/kusaanko/Blender_XFileSupport_BVE
#
# Copyright (c) 2021 kusaanko
# This is licensed under the Apache License 2.0
# see https://github.com/kusaanko/Blender_XFileSupport_BVE/blob/main/LICENSE

import os
import re
import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
import urllib.request
import urllib.parse
import json
import webbrowser

bl_info = {
    "name": "Import/Export DirectX X File (.x) for Bve",
    "author": "kusaanko",
    "version": (1, 2, 0),
    "blender": (2, 80, 3),
    "location": "File > Import / Export > DirectX XFile(.x)",
    "description": "Import/Export files in the DirectX X file (.x)",
    "warning": "This plug-in is for Bve. So some features are not supported.",
    "wiki_url": "https://github.com/kusaanko/Blender_XFileSupport_BVE/wiki",
    "tracker_url": "",
    "category": "Import-Export"
}

__version__ = "1.1.0"

# locale
#    (target_context, key): translated_str
translations_dict = {
    "ja_JP": {
        ("*", "Remove All Objects and Materials"): "全てのオブジェクトとマテリアルを削除する",
        ("*", "The update of XFileSupport is available!"): "XFileSupportの更新が利用可能です！",
        ("*", "Your version:"): "現在のバージョン:",
        ("*", "New version:"): "新しいバージョン:",
        ("*", "Please download from this link."): "このリンクからダウンロードしてください。"
    }
}


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
                # Blender -X -Z Y
                vector = (-vertex[0], -vertex[2], vertex[1])
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
        for tex in element.children:
            if tex.element_type == "TextureFilename":
                path = "/".join(os.path.abspath(self.filepath).split(os.path.sep)[0:-1])
                name = tex.data[tex.data.find("\"") + 1:tex.data.rfind("\"")]
                path = path + "/" + name
                if os.path.exists(path):
                    material.texture_path = path
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

            vector_index = 0

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
                # マテリアルの有無
                available_material = len(self.materials) > self.material_face_indexes[faces[0]]
                x_material = self.materials[self.material_face_indexes[faces[0]]]
                # マテリアルを作成
                material = bpy.data.materials.new(model_name + "Material")

                color = (1.0, 1.0, 1.0)
                material.specular_intensity = 0.0
                if available_material:
                    color = x_material.face_color
                    material.specular_intensity = x_material.power
                    material.specular_color = x_material.specular_color
                material.diffuse_color = color

                # ブレンドモードの設定
                material.blend_method = 'CLIP'
                material.shadow_method = 'CLIP'

                # テクスチャの紐付け
                if x_material.texture_path != "":
                    # ノードを有効化
                    material.use_nodes = True

                    # 画像ノードを作成
                    texture = material.node_tree.nodes.new("ShaderNodeTexImage")
                    texture.location = (-300, 300)

                    # 画像を読み込み
                    texture.image = bpy.data.images.load(filepath=x_material.texture_path)
                    nodes = material.node_tree.nodes
                    # プリンシプルBSDFを取得
                    principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
                    # ベースカラーとテクスチャのカラーをリンクさせる
                    material.node_tree.links.new(principled.inputs['Base Color'], texture.outputs['Color'])
                    # アルファとテクスチャのアルファをリンクさせる
                    material.node_tree.links.new(principled.inputs['Alpha'], texture.outputs['Alpha'])

                    # スペキュラーを設定
                    principled.inputs['Specular'].default_value = x_material.power
                    if not (x_material.specular_color[0] == x_material.specular_color[1] and
                            x_material.specular_color[1] == x_material.specular_color[2]):
                        rgb = material.node_tree.nodes.new("ShaderNodeRGB")
                        rgb.location = (-300, 0)
                        for out in rgb.outputs:
                            if out.type == 'RGBA':
                                color = []
                                color.extend(x_material.specular_color)
                                color.append(1.0)
                                out.default_value = color
                        material.node_tree.links.new(principled.inputs['Specular'], rgb.outputs['Color'])

                    # 放射を設定
                    principled.inputs['Emission'].default_value = x_material.emission_color

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

    def execute(self, context):
        if not self.filepath.endswith(".x"):
            return {'CANCELLED'}
        x_file_content = '''xof 0302txt 0032

Header {
 1;
 0;
 1;
}

'''
        vertexes = []
        vertexes_dict = {}
        normals = []
        normals_dict = {}
        vertex_use_normal = []
        faces = []
        materials_dict = {}
        materials = []
        faces_use_material = []
        uv_data = []
        fake_material = gen_fake_material()

        for obj in bpy.context.scene.objects:
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
                    for vertex in polygon.vertices:
                        vertex_co = mesh.vertices[vertex].co
                        # スケールに合わせる
                        vertex_co[0] *= self.scale
                        vertex_co[1] *= self.scale
                        vertex_co[2] *= self.scale
                        # 頂点が他のデータと重複していたらそれを使用する
                        # 頂点とUVはセットなのでセットで重複を調べる
                        if vertex_to_str(vertex_co) + str(uv_vertexes[vertex_index]) \
                                not in vertexes_dict.keys():
                            vertexes_dict[vertex_to_str(vertex_co) + str(uv_vertexes[vertex_index])] \
                                = len(vertexes_dict.keys())
                            vertexes.append(vertex_co)
                            uv_data.append(uv_vertexes[vertex_index])
                        if vertex_to_str(mesh.vertices[vertex].normal) not in normals_dict.keys():
                            normals_dict[vertex_to_str(mesh.vertices[vertex].normal)] = len(normals_dict.keys())
                            normals.append(mesh.vertices[vertex].normal)
                        ver.append(vertexes_dict[vertex_to_str(vertex_co) + str(uv_vertexes[vertex_index])])
                        normal.append(normals_dict[vertex_to_str(mesh.vertices[vertex].normal)])
                        vertex_index += 1
                    faces.append(ver)
                    vertex_use_normal.append(normal)
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
                        faces_use_material.append(materials_dict[mesh.materials[0].name])
                # for vertex in mesh.uv_layers[0].data:
                #    uv_data.append(vertex)

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

        for material in materials:
            x_file_content += "  Material {\n"
            # ノードを使用するかどうか
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
                            texture = os.path.relpath(
                                link.from_node.image.filepath,
                                "/".join(os.path.abspath(self.filepath).split(os.path.sep)[0:-1])
                            )
                        if link.from_node.type == "RGB":
                            need_color = False
                            for out in link.from_node.outputs:
                                if out.type == 'RGBA':
                                    color = out.default_value
                                    x_file_content += "   " + \
                                                      str(round(color[0], 6)) + ";" + \
                                                      str(round(color[1], 6)) + ";" + \
                                                      str(round(color[2], 6)) + ";" + \
                                                      str(round(color[3], 6)) + ";;\n"
                    if need_color:
                        x_file_content += "   1.000000;1.000000;1.000000;1.000000;;\n"
                else:
                    color = principled.inputs['Base Color'].default_value
                    x_file_content += "   " + \
                                      str(round(color[0], 6)) + ";" + \
                                      str(round(color[1], 6)) + ";" + \
                                      str(round(color[2], 6)) + ";" + \
                                      str(round(color[3], 6)) + ";;\n"
                # 鏡面反射
                x_file_content += "   " + str(principled.inputs['Specular'].default_value) + ";\n"
                # 鏡面反射色
                if len(principled.inputs['Specular'].links) > 0:
                    for link in principled.inputs['Specular'].links:
                        if link.from_node.type == "RGB":
                            for out in link.from_node.outputs:
                                if out.type == 'RGBA':
                                    x_file_content += "   " + \
                                                      str(round(out.default_value[0], 6)) + ";" + \
                                                      str(round(out.default_value[1], 6)) + ";" + \
                                                      str(round(out.default_value[2], 6)) + ";;\n"
                                    break
                else:
                    power = str(round(principled.inputs['Specular'].default_value, 6))
                    x_file_content += "   " + power + ";" + power + ";" + power + ";;\n"

                # 放射色
                x_file_content += "   " + \
                                  str(round(principled.inputs['Emission'].default_value[0], 6)) + ";" + \
                                  str(round(principled.inputs['Emission'].default_value[1], 6)) + ";" + \
                                  str(round(principled.inputs['Emission'].default_value[2], 6)) + ";;\n"

                if texture != "":
                    x_file_content += "\n   TextureFilename {\n"
                    x_file_content += "    \"" + texture + "\";\n"
                    x_file_content += "   }\n"
            else:
                # ベースカラー
                color = material.diffuse_color
                x_file_content += "   " + \
                                  str(round(color[0], 6)) + ";" + \
                                  str(round(color[1], 6)) + ";" + \
                                  str(round(color[2], 6)) + ";1.000000;;\n"
                # 鏡面反射
                x_file_content += "   " + str(material.specular_intensity) + ";\n"
                # 鏡面反射色
                x_file_content += "   " + \
                                  str(round(material.specular_color[0], 6)) + ";" + \
                                  str(round(material.specular_color[1], 6)) + ";" + \
                                  str(round(material.specular_color[2], 6)) + ";;\n"
                # 放射色
                x_file_content += "   0.000000;0.000000;0.000000;;\n"
                # x_file_content += "   " + \
                #                  str(principled.inputs['Emission'].default_value[0]) + ";" + \
                #                  str(principled.inputs['Emission'].default_value[1]) + ";" + \
                #                  str(principled.inputs['Emission'].default_value[2]) + ";;\n"
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
            x_file_content += "  " + str(round(vertex.uv[0], 6)) + ";" + str(round(-vertex.uv[1] + 1, 6)) + ";,\n"
        x_file_content = x_file_content[0:-2] + ";\n"
        x_file_content += " }\n"
        x_file_content += "}\n"

        # 生成した偽物のマテリアルを削除
        fake_material.user_clear()
        bpy.data.materials.remove(fake_material)

        with open(self.filepath, mode='w') as f:
            f.write(x_file_content)

        return {'FINISHED'}


def menu_func_import(self, context):
    if bpy.context.mode != "OBJECT":
        return
    self.layout.operator(ImportDirectXXFile.bl_idname, text="DirectX XFile (.x)")


def menu_func_export(self, context):
    if bpy.context.mode != "OBJECT":
        return
    self.layout.operator(ExportDirectXXFile.bl_idname, text="DirectX XFile (.x)")


def register():
    bpy.utils.register_class(ImportDirectXXFile)
    bpy.utils.register_class(ExportDirectXXFile)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    bpy.app.translations.register(__name__, translations_dict)

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
    except OSError:
        pass


def unregister():
    bpy.app.translations.unregister(__name__)

    bpy.utils.unregister_class(ImportDirectXXFile)
    bpy.utils.unregister_class(ExportDirectXXFile)

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
                    element_type = element_type[0:element_type.find(" ")]
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
    return result


def vertex_to_str(vertex):
    # Blender X Z Y
    # DirectX -X Y Z
    return str(round(-vertex[0], 6)) + ";" + str(round(vertex[2], 6)) + ";" + str(round(-vertex[1], 6))


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


class XElement:
    element_type = ""
    data = ""
    children = []
    end_line_num = 0


class XMaterial:
    face_color = ()
    power = 0.0
    specular_color = ()
    emission_color = ()
    texture_path = ""


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
