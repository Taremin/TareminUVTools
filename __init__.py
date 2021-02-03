import bmesh
import bpy
import mathutils

bl_info = {
    'name': 'Taremin UV Tools',
    'author': (
        'Taremin'
    ),
    'version': (0, 0, 2),
    'blender': (2, 80, 0),
    'location': 'UV Editor > Context Menu',
    'description': '',
    'warning': '',
    'wiki_url': '',
    'category': 'UV'
}


def menu_func(self, context):
    label = IMAGE_MT_taremin_uv_tools_menu.bl_label
    if get_sync(context):
        label += '(同期モード使用不可)'
        self.layout.label(text=label)
    else:
        self.layout.menu(IMAGE_MT_taremin_uv_tools_menu.bl_idname)


def get_sync(context):
    return context.scene.tool_settings.use_uv_select_sync


class SelectedUV:
    vertex: int
    uv: mathutils.Vector

    def __init__(self, vertex: bmesh.types.BMVert, uv: mathutils.Vector):
        self.vertex = vertex
        self.uv = uv

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, vars(self))


class Util:
    conditions = {
        'LEFT': lambda a, b: a.uv[0] > b.uv[0],
        'RIGHT': lambda a, b: a.uv[0] < b.uv[0],
        'TOP': lambda a, b: a.uv[1] < b.uv[1],
        'BOTTOM': lambda a, b: a.uv[1] > b.uv[1],
    }

    def select_bound_uv(self, obj, func, dryrun=False):
        bpy.ops.object.editmode_toggle()
        bpy.ops.object.editmode_toggle()

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        prev = None
        vertex_index_to_loop_uvs = {}
        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                if luv.select:
                    if not dryrun:
                        luv.select = False

                    if l.vert.index not in vertex_index_to_loop_uvs:
                        vertex_index_to_loop_uvs[l.vert.index] = []
                    vertex_index_to_loop_uvs[l.vert.index].append(luv)

                    if prev is None or func(prev[uv_layer], l[uv_layer]):
                        prev = l
        if prev is not None:
            for luv in vertex_index_to_loop_uvs[prev.vert.index]:
                # 同じ頂点indexでも別のUVを刺している場合があるので端であるprevと比較
                if prev[uv_layer].uv == luv.uv:
                    if not dryrun:
                        luv.select = True
                    else:
                        return luv.uv.copy()
        bmesh.update_edit_mesh(obj.data)


class UV_OT_taremin_uv_mirror_axis_setter(bpy.types.Operator):
    bl_idname = 'uv.taremin_uv_mirror_axis_setter'
    bl_label = 'Set Mirror Modifier Offset by selected UV'
    bl_description = '選択頂点のUV座標を選択ミラーモディファイアの反転オフセットにセットします'
    bl_options = {'REGISTER', 'UNDO'}

    modifier_name: bpy.props.StringProperty(default='')
    axis: bpy.props.StringProperty(default='')

    def execute(self, context):
        obj = context.object
        modifier = obj.modifiers[self.modifier_name]

        selected_uvs = self.get_selected_uvs(obj)
        if len(selected_uvs) != 1:
            self.report(type={'ERROR'}, message="選択頂点が1個のときに使用できます")
            return {'CANCELLED'}

        if self.axis == 'U':
            modifier.use_mirror_u = True
            modifier.mirror_offset_u = (-1 - modifier.offset_u) + selected_uvs[0].uv[0] * 2
        elif self.axis == 'V':
            modifier.use_mirror_v = True
            modifier.mirror_offset_v = (-1 - modifier.offset_v) + selected_uvs[0].uv[1] * 2
        else:
            self.report(type={'ERROR'}, message='不正な状態です')

        return {'FINISHED'}

    def get_selected_uvs(self, obj):
        bpy.ops.object.editmode_toggle()
        bpy.ops.object.editmode_toggle()

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        dict = {}
        uvs = []
        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                if luv.select:
                    dict[l.vert.index] = luv.uv.copy()
                    uvs.append(luv.uv.copy())

        return [SelectedUV(index, dict[index]) for index in dict.keys()]


class UV_OT_taremin_uv_array_axis_setter(bpy.types.Operator, Util):
    bl_idname = 'uv.taremin_uv_array_axis_setter'
    bl_label = 'Set Array Modifier Offset by selected UV'
    bl_description = '選択頂点のUV座標を配列ミラーモディファイアのオフセットにセットします'

    modifier_name: bpy.props.StringProperty(default='')
    axis: bpy.props.StringProperty(default='')

    def execute(self, context):
        obj = context.object
        modifier = obj.modifiers[self.modifier_name]

        bounding_uv = {}
        for position in ('LEFT', 'RIGHT', 'TOP', 'BOTTOM'):
            bounding_uv[position] = self.select_bound_uv(
                context.active_object,
                self.conditions[position],
                True
            )

        if self.axis == 'U':
            modifier.offset_u = bounding_uv['RIGHT'][0] - bounding_uv['LEFT'][0]
        elif self.axis == 'V':
            modifier.offset_v = bounding_uv['TOP'][1] - bounding_uv['BOTTOM'][1]
        else:
            self.report(type={'ERROR'}, message='不正な状態です')

        return {'FINISHED'}


class UV_OT_taremin_uv_bouding_point(bpy.types.Operator, Util):
    bl_idname = 'uv.taremin_uv_bounding_point'
    bl_label = 'select bounding point'
    bl_description = '選択頂点の中から上下左右の端を選択します'
    bl_options = {'REGISTER', 'UNDO'}

    position: bpy.props.StringProperty()

    def execute(self, context):
        self.select_bound_uv(context.active_object, self.conditions[self.position])

        return {'FINISHED'}


class IMAGE_MT_taremin_uv_tools_mirror_axis_menu(bpy.types.Menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_mirror_axis_menu'
    bl_label = 'UV Mirror Tools SubMenu'

    axis: bpy.props.StringProperty()

    def draw(self, context):
        obj = context.object

        layout = self.layout
        col = layout.column()

        for i in range(len(obj.modifiers)):
            modifier = obj.modifiers[i]
            if modifier.type == 'MIRROR':
                op = col.operator(UV_OT_taremin_uv_mirror_axis_setter.bl_idname, text=modifier.name, translate=False)
                op.modifier_name = obj.modifiers[i].name
                op.axis = self.axis


class IMAGE_MT_taremin_uv_tools_mirror_axis_u_menu(IMAGE_MT_taremin_uv_tools_mirror_axis_menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_mirror_axis_u_menu'
    axis = 'U'


class IMAGE_MT_taremin_uv_tools_mirror_axis_v_menu(IMAGE_MT_taremin_uv_tools_mirror_axis_menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_mirror_axis_v_menu'
    axis = 'V'


class IMAGE_MT_taremin_uv_tools_array_axis_menu(bpy.types.Menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_array_axis_menu'
    bl_label = 'UV Mirror Tools SubMenu'

    axis: bpy.props.StringProperty()

    def draw(self, context):
        obj = context.object

        layout = self.layout
        col = layout.column()

        for i in range(len(obj.modifiers)):
            modifier = obj.modifiers[i]
            if modifier.type == 'ARRAY':
                op = col.operator(UV_OT_taremin_uv_array_axis_setter.bl_idname, text=modifier.name, translate=False)
                op.modifier_name = obj.modifiers[i].name
                op.axis = self.axis


class IMAGE_MT_taremin_uv_tools_array_axis_u_menu(IMAGE_MT_taremin_uv_tools_array_axis_menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_array_axis_u_menu'
    axis = 'U'


class IMAGE_MT_taremin_uv_tools_array_axis_v_menu(IMAGE_MT_taremin_uv_tools_array_axis_menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_array_axis_v_menu'
    axis = 'V'


class IMAGE_MT_taremin_uv_tools_mirror_menu(bpy.types.Menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_mirror_menu'
    bl_label = 'Mirror'

    @classmethod
    def poll(cls, context):
        return not get_sync(context)

    def draw(self, context):
        layout = self.layout
        layout.menu(IMAGE_MT_taremin_uv_tools_mirror_axis_u_menu.bl_idname, text='U軸反転オフセットを設定')
        layout.menu(IMAGE_MT_taremin_uv_tools_mirror_axis_v_menu.bl_idname, text='V軸反転オフセットを設定')

        # select one uv
        op = layout.operator(UV_OT_taremin_uv_bouding_point.bl_idname, text='左端の選択頂点以外選択解除')
        op.position = 'LEFT'
        op = layout.operator(UV_OT_taremin_uv_bouding_point.bl_idname, text='右端の選択頂点以外選択解除')
        op.position = 'RIGHT'
        op = layout.operator(UV_OT_taremin_uv_bouding_point.bl_idname, text='上端の選択頂点以外選択解除')
        op.position = 'TOP'
        op = layout.operator(UV_OT_taremin_uv_bouding_point.bl_idname, text='下端の選択頂点以外選択解除')
        op.position = 'BOTTOM'


class IMAGE_MT_taremin_uv_tools_array_menu(bpy.types.Menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_array_menu'
    bl_label = 'Array'

    @classmethod
    def poll(cls, context):
        return not get_sync(context)

    def draw(self, context):
        layout = self.layout
        layout.menu(IMAGE_MT_taremin_uv_tools_array_axis_u_menu.bl_idname, text='U軸オフセットを設定')
        layout.menu(IMAGE_MT_taremin_uv_tools_array_axis_v_menu.bl_idname, text='V軸オフセットを設定')


class IMAGE_MT_taremin_uv_tools_menu(bpy.types.Menu):
    bl_idname = 'IMAGE_MT_taremin_uv_tools_menu'
    bl_label = 'Taremin UV Tools'

    @classmethod
    def poll(cls, context):
        return not get_sync(context)

    def draw(self, context):
        layout = self.layout
        layout.menu(IMAGE_MT_taremin_uv_tools_mirror_menu.bl_idname, text='Mirror Modifier')
        layout.menu(IMAGE_MT_taremin_uv_tools_array_menu.bl_idname, text='Array Modifier')


register_classes = [
    UV_OT_taremin_uv_mirror_axis_setter,
    IMAGE_MT_taremin_uv_tools_menu,
    IMAGE_MT_taremin_uv_tools_mirror_menu,
    IMAGE_MT_taremin_uv_tools_mirror_axis_u_menu,
    IMAGE_MT_taremin_uv_tools_mirror_axis_v_menu,
    UV_OT_taremin_uv_array_axis_setter,
    IMAGE_MT_taremin_uv_tools_array_menu,
    IMAGE_MT_taremin_uv_tools_array_axis_u_menu,
    IMAGE_MT_taremin_uv_tools_array_axis_v_menu,
    UV_OT_taremin_uv_bouding_point,
]


def register():
    for cls in register_classes:
        bpy.utils.register_class(cls)
    bpy.types.IMAGE_MT_uvs_context_menu.append(menu_func)


def unregister():
    for cls in register_classes:
        bpy.utils.unregister_class(cls)
    bpy.types.IMAGE_MT_uvs_context_menu.remove(menu_func)


if __name__ == '__main__':
    register()
