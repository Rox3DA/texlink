import bpy


class TEXLINK_OT_refresh_cycles(bpy.types.Operator):
    bl_idname = "texlink.refresh_cycles"
    bl_label = "Refresh Cycles"
    bl_description = (
        "Force Cycles rendered viewports to re-sync reloaded textures "
        "(toggles shading RENDERED->SOLID->RENDERED). Use after painting in SP "
        "if the Cycles viewport hasn't updated"
    )

    def execute(self, context):
        # Ricarica le immagini del materiale attivo (sicurezza, oltre al watcher)
        obj = context.active_object
        if obj and obj.type == "MESH":
            mat = obj.active_material
            if mat and mat.use_nodes:
                for n in mat.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image:
                        n.image.reload()

        # Toggle shading sui viewport Rendered (in contesto operatore funziona sincrono)
        count = 0
        for area in context.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D" and space.shading.type == "RENDERED":
                    space.shading.type = "SOLID"
                    space.shading.type = "RENDERED"
                    count += 1
            area.tag_redraw()

        if count:
            self.report({"INFO"}, f"Refreshed {count} Cycles viewport(s)")
        else:
            self.report({"INFO"}, "No Cycles 'Rendered' viewport found")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(TEXLINK_OT_refresh_cycles)


def unregister():
    bpy.utils.unregister_class(TEXLINK_OT_refresh_cycles)
