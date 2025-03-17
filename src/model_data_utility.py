import re
import bpy
import math
import os

from .utility import vertex_to_str

class Material:
    face_color = ()
    power = 0.0
    specular_color = ()
    emission_color = ()
    texture_path = ""
    name = ""

def gen_fake_material():
    # 偽物のマテリアルを作成 / Create a fake material
    material = bpy.data.materials.new("NoneMaterial")

    material.specular_intensity = 0.0
    material.specular_color = (0.0, 0.0, 0.0)
    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)

    # ブレンドモードの設定 / Set blend mode
    material.blend_method = 'CLIP'

    # ノードを有効化 / Enable nodes
    material.use_nodes = True

    nodes = material.node_tree.nodes
    # プリンシプルBSDFを取得 / Get the Principled BSDF
    principled = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')

    # ベースカラーを設定 / Set the base color
    principled.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)

    # スペキュラーを設定 / Set the specular
    principled.inputs['Specular Tint'].default_value = (1.0, 1.0, 1.0, 1.0)
    principled.inputs['Specular IOR Level'].default_value = 0.5

    # 放射を設定 / Set the emission
    principled.inputs['Emission Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    return material

# 出力用にデータを整形
class ModelDataUtility:
    def __init__(self):
        self.vertexes = []
        self.normals = []
        self.vertex_use_normal = []
        self.faces = []
        self.x_materials = []
        self.faces_use_material = []
        self.uv_data = []

    def execute(self, context, export_selected_only: bool, scale: float, gamma_correction: bool):
        self.vertexes = []
        vertexes_dict = {}
        self.normals = []
        normals_dict = {}
        self.vertex_use_normal = []
        self.faces = []
        materials_dict: list[int] = {}
        materials = []
        self.x_materials: list[Material] = []
        self.faces_use_material = []
        self.uv_data = []
        fake_material = gen_fake_material()

        target_objects = bpy.context.scene.objects
        if export_selected_only:
            target_objects = bpy.context.selected_objects
        for obj in target_objects:
            if obj.type == 'MESH' and not obj.hide_get():
                # モディファイヤーを適用した状態のオブジェクトを取得
                depsgraph = bpy.context.evaluated_depsgraph_get()
                obj_tmp = obj.evaluated_get(depsgraph)

                # Meshに変換
                mesh = obj_tmp.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
                
                uv_vertexes = mesh.uv_layers.active.data
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
                        self.faces_use_material.append(materials_dict[fake_material.name])
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
                        self.faces_use_material.append(materials_dict[mesh.materials[polygon.material_index].name])

                    for vertex in reversed(polygon.vertices):
                        # ワールド座標から変換
                        vertex_co = obj.matrix_world @ mesh.vertices[vertex].co
                        # スケールに合わせる
                        vertex_co[0] *= scale
                        vertex_co[1] *= scale
                        vertex_co[2] *= scale
                        # 頂点が他のデータと重複していたらそれを使用する
                        # 頂点とUVはセットなのでセットで重複を調べる
                        uv = uv_vertexes[vertex_index].uv
                        if texture == "":
                            uv = (0.0, 0.0)
                        key = vertex_to_str(vertex_co) + str(uv)
                        if key not in vertexes_dict.keys():
                            vertexes_dict[key] = len(vertexes_dict.keys())
                            self.vertexes.append(vertex_co)
                            self.uv_data.append(uv)
                        if smooth_shading:
                            nor = mesh.vertices[vertex].normal
                        if vertex_to_str(nor) not in normals_dict.keys():
                            normals_dict[vertex_to_str(nor)] = len(normals_dict.keys())
                            self.normals.append(nor)
                        ver.append(vertexes_dict[key])
                        normal.append(normals_dict[vertex_to_str(nor)])
                        vertex_index -= 1
                    vertex_index += len(polygon.vertices) + 1
                    self.faces.append(ver)
                    self.vertex_use_normal.append(normal)

        for material in materials:
            # ノードを使用するかどうか
            x_material = Material()
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
                                    x_material.face_color = [out.default_value[0], out.default_value[1], out.default_value[2], principled.inputs['Alpha'].default_value]
                                    if gamma_correction:
                                        x_material.face_color[0] = math.pow(x_material.face_color[0], 1/2.2)
                                        x_material.face_color[1] = math.pow(x_material.face_color[1], 1/2.2)
                                        x_material.face_color[2] = math.pow(x_material.face_color[2], 1/2.2)
                        if link.from_node.type == "GAMMA":
                            for input in link.from_node.inputs:
                                if input.identifier == 'Gamma':
                                    if round(input.default_value * 100) != 220:
                                        raise Exception(bpy.app.translations.pgettext("Gamma correction is not 2.2"))
                                if input.identifier == 'Color':
                                    need_color = False
                                    x_material.face_color = (input.default_value[0], input.default_value[1], input.default_value[2], principled.inputs['Alpha'].default_value)
                    if need_color:
                        x_material.face_color = (1.0, 1.0, 1.0, 1.0)
                else:
                    col = principled.inputs['Base Color'].default_value
                    x_material.face_color = [col[0], col[1], col[2], principled.inputs['Alpha'].default_value]
                    if gamma_correction:
                        x_material.face_color[0] = math.pow(x_material.face_color[0], 1/2.2)
                        x_material.face_color[1] = math.pow(x_material.face_color[1], 1/2.2)
                        x_material.face_color[2] = math.pow(x_material.face_color[2], 1/2.2)
                # 鏡面反射
                x_material.power = principled.inputs['Specular IOR Level'].default_value
                x_material.specular_color = principled.inputs['Specular Tint'].default_value

                # 放射色
                x_material.emission_color = principled.inputs['Emission Color'].default_value

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
            self.x_materials.append(x_material)
            
        # 生成した偽物のマテリアルを削除
        fake_material.user_clear()
        
        bpy.data.materials.remove(fake_material)