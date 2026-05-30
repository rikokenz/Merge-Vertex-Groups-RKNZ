bl_info = {
    "name": "Merge Vertex Groups RKNZ",
    "author": "Rikokenz",
    "version": (1, 2, 0),
    "blender": (4, 2, 0),
    "location": "Properties > Object Data > Vertex Groups",
    "description": "Combine multiple vertex groups into one using Max, Add, or Average weight blending.",
    "category": "Mesh",
}

import bpy
from bpy.props import StringProperty, EnumProperty, CollectionProperty, BoolProperty


# ── Property groups ───────────────────────────────────────────────────────────

class RKNZ_MVG_GroupEntry(bpy.types.PropertyGroup):
    selected: BoolProperty(name="", default=False)


class RKNZ_MVG_SceneProps(bpy.types.PropertyGroup):
    group_entries: CollectionProperty(type=RKNZ_MVG_GroupEntry)


# ── Operator ──────────────────────────────────────────────────────────────────

class MESH_OT_rknz_merge_vertex_groups(bpy.types.Operator):
    """Merge selected vertex groups into a new vertex group"""
    bl_idname = "mesh.rknz_merge_vertex_groups"
    bl_label = "Merge Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}

    new_group_name: StringProperty(
        name="New Group Name",
        default="merged",
    )

    mix_mode: EnumProperty(
        name="Mix Mode",
        items=[
            ('MAX',     "Max",     "Use the highest weight across selected groups"),
            ('ADD',     "Add",     "Add weights together, clamped to 1.0"),
            ('AVERAGE', "Average", "Average weight across groups that contain the vertex"),
        ],
        default='MAX',
    )

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.active_object.type == 'MESH'
            and len(context.active_object.vertex_groups) >= 2
        )

    def invoke(self, context, event):
        obj = context.active_object
        props = context.scene.rknz_mvg_props
        props.group_entries.clear()
        for vg in obj.vertex_groups:
            entry = props.group_entries.add()
            entry.name = vg.name
            entry.selected = False
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        props = context.scene.rknz_mvg_props

        layout.prop(self, "new_group_name")
        layout.prop(self, "mix_mode")
        layout.separator()
        layout.label(text="Select groups to merge:")

        box = layout.box()
        col = box.column(align=True)
        for entry in props.group_entries:
            row = col.row(align=True)
            row.prop(entry, "selected")
            row.label(text=entry.name)

        count = sum(1 for e in props.group_entries if e.selected)
        layout.label(text=f"{count} group(s) selected", icon='INFO')

    def execute(self, context):
        obj = context.active_object
        props = context.scene.rknz_mvg_props

        selected_names = [e.name for e in props.group_entries if e.selected]

        if len(selected_names) < 2:
            self.report({'WARNING'}, "Select at least 2 vertex groups to merge")
            return {'CANCELLED'}

        src_groups = [obj.vertex_groups.get(n) for n in selected_names if obj.vertex_groups.get(n)]

        if not src_groups:
            self.report({'WARNING'}, "No valid vertex groups found")
            return {'CANCELLED'}

        dst_name = self.new_group_name.strip() or "merged"
        existing = {vg.name for vg in obj.vertex_groups}
        if dst_name in existing:
            counter = 1
            while f"{dst_name}.{counter:03d}" in existing:
                counter += 1
            dst_name = f"{dst_name}.{counter:03d}"

        dst = obj.vertex_groups.new(name=dst_name)

        for v in obj.data.vertices:
            weights = []
            for vg in src_groups:
                try:
                    weights.append(vg.weight(v.index))
                except RuntimeError:
                    pass

            if not weights:
                continue

            if self.mix_mode == 'MAX':
                final = max(weights)
            elif self.mix_mode == 'ADD':
                final = min(sum(weights), 1.0)
            elif self.mix_mode == 'AVERAGE':
                final = sum(weights) / len(weights)

            if final > 0.0:
                dst.add([v.index], final, 'REPLACE')

        self.report({'INFO'}, f"Merged {len(src_groups)} groups into '{dst_name}'")
        return {'FINISHED'}


# ── Button injected into Vertex Groups panel ──────────────────────────────────

def draw_merge_button(self, context):
    if context.active_object and context.active_object.type == 'MESH':
        self.layout.operator("mesh.rknz_merge_vertex_groups", icon='GROUP_VERTEX')


# ── Register ──────────────────────────────────────────────────────────────────

classes = (
    RKNZ_MVG_GroupEntry,
    RKNZ_MVG_SceneProps,
    MESH_OT_rknz_merge_vertex_groups,
)


def _get_vg_panel():
    if hasattr(bpy.types, "DATA_PT_vertex_groups"):
        return bpy.types.DATA_PT_vertex_groups
    if hasattr(bpy.types, "DATA_PT_mesh_vertex_groups"):
        return bpy.types.DATA_PT_mesh_vertex_groups
    return None


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.rknz_mvg_props = bpy.props.PointerProperty(
        type=RKNZ_MVG_SceneProps,
    )
    panel = _get_vg_panel()
    if panel is not None:
        panel.append(draw_merge_button)


def unregister():
    panel = _get_vg_panel()
    if panel is not None:
        panel.remove(draw_merge_button)
    del bpy.types.Scene.rknz_mvg_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
