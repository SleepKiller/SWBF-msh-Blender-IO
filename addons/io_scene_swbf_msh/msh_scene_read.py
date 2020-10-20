""" Contains functions for saving a Scene to a .msh file.  """

from itertools import islice
from typing import Dict
from .msh_scene import Scene
from .msh_model import *
from .msh_material import *
from .msh_reader import Reader
from .msh_utilities import *

from .crc import *

def read_scene(input_file) -> Scene:

    scene = Scene()
    scene.models = []

    with Reader(file=input_file, chunk_id="HEDR") as hedr:
        with hedr.read_child("MSH2") as msh2:

            with msh2.read_child("SINF") as sinf:
                pass

            materials_list: List[str] = []

            with msh2.read_child("MATL") as matl:
                materials_list = _read_matl_and_get_materials_list(matl)

            while ("MODL" in msh2.peak_next_header()):
                with msh2.read_child("MODL") as modl:
                    scene.models.append(_read_modl(modl, materials_list))

            mats_dict = {}
            for i,mat in enumerate(materials_list):
                mats_dict["Material" + str(i)] = mat

            scene.materials = mats_dict

        #with hedr.read_child("ANM2") as anm2: #simple for now
        #    for anim in scene.anims:
        #        _write_anm2(anm2, anim)

        #with hedr.read_child("CL1L"):
        #    pass



    return scene


def _read_matl_and_get_materials_list(matl: Reader) -> List[str]:
    materials_list: List[str] = []

    num_mats = matl.read_u32()

    for _ in range(num_mats):
        with matl.read_child("MATD") as matd:
            materials_list.append(_read_matd(matd))

    return materials_list



def _read_matd(matd: Reader) -> Material:

    mat = Material()

    while matd.could_have_child():

        next_header = matd.peak_next_header()

        if "NAME" in next_header:
            with matd.read_child("NAME") as name:
                mat.name = name.read_string()
            print(matd.indent + "Got a new material: " + mat.name)

        elif "DATA" in next_header:
            with matd.read_child("DATA") as data:
                data.read_f32(4) # Diffuse Color (Seams to get ignored by modelmunge)
                mat.specular_color = data.read_f32(4)
                data.read_f32(4) # Ambient Color (Seams to get ignored by modelmunge and Zero(?))
                data.read_f32()  # Specular Exponent/Decay (Gets ignored by RedEngine in SWBFII for all known materials)    
    
        elif "ATRB" in next_header:
            with matd.read_child("ATRB") as atrb:
                mat.flags = atrb.read_u8()
                mat.rendertype = atrb.read_u8()
                mat.data = atrb.read_u8(2)

        elif "TX0D" in next_header:
            with matd.read_child("TX0D") as tx0d:
                mat.texture0 = tx0d.read_string()

        elif "TX1D" in next_header:
            with matd.read_child("TX1D") as tx1d:
                mat.texture1 = tx1d.read_string()

        elif "TX2D" in next_header:
            with matd.read_child("TX2D") as tx2d:
                mat.texture2 = tx2d.read_string()

        elif "TX3D" in next_header:
            with matd.read_child("TX3D") as tx3d:
                mat.texture3 = tx3d.read_string()

        else:
            matd.skip_bytes(4)

    return mat


def _read_modl(modl: Reader, materials_list: List[str]) -> Model:

    model = Model()

    while modl.could_have_child():

        next_header = modl.peak_next_header()

        if "MTYP" in next_header:
            with modl.read_child("MTYP") as mtyp:
                model.model_type = mtyp.read_u32()

        elif "MNDX" in next_header:
            with modl.read_child("MNDX") as mndx:
                pass

        elif "NAME" in next_header:
            with modl.read_child("NAME") as name:
                model.name = name.read_string()
            print(modl.indent + "New model: " + model.name)

        elif "PRNT" in next_header:
            with modl.read_child("PRNT") as prnt:
                model.parent = prnt.read_string()

        elif "FLGS" in next_header:
            with modl.read_child("FLGS") as flgs:
                model.hidden = flgs.read_u32()

        elif "TRAN" in next_header:
            with modl.read_child("TRAN") as tran:
                model.transform = _read_tran(tran)

        elif "GEOM" in next_header:
            model.geometry = []
            with modl.read_child("GEOM") as geom:

                next_header_modl = geom.peak_next_header()

                if "SEGM" in next_header_modl:
                    with geom.read_child("SEGM") as segm:
                       model.geometry.append(_read_segm(segm, materials_list))
            '''
            if model.model_type == ModelType.SKIN:
                with modl.read_child("ENVL") as envl:
                    envl.write_u32(len(scene.models))
                    for i in range(len(scene.models)):
                        envl.write_u32(i)
            '''
        elif "SWCI" in next_header:
            prim = CollisionPrimitive()
            with modl.read_child("SWCI") as swci:
                prim.shape.value = swci.read_u32()
                prim.radius = swci.read_f32()
                prim.height = swci.read_f32()
                prim.length = swci.read_f32()
            model.collisionprimitive = prim

        else:
            with modl.read_child("NULL") as unknown:
                pass



def _read_tran(tran: Reader) -> ModelTransform:

    xform = ModelTransform()

    tran.skip_bytes(4 * 3) #ignore scale
    xform.rotation = Quaternion(tran.read_f32(4))
    xform.position = Vector(tran.read_f32(3))

    return xform



def _read_segm(segm: Reader, materials_list: List[str]) -> GeometrySegment:

    geometry_seg = GeometrySegment()

    while segm.could_have_child():

        next_header = segm.peak_next_header()

        if "MATI" in next_header:
            with segm.read_child("MATI") as mati:
                geometry_seg.material_name = materials_list[mati.read_u32()]

        elif "POSL" in next_header:
            with segm.read_child("POSL") as posl:
                num_positions = posl.read_u32()

                for _ in range(num_positions):
                    geometry_seg.positions.append(Vector(posl.read_f32(3)))

        elif "NRML" in next_header:
            with segm.read_child("NRML") as nrml:
                num_normals = nrml.read_u32()
                
                for _ in range(num_positions):
                    geometry_seg.normals.append(Vector(nrml.read_f32(3))) 

        elif "WGHT" in next_header:
            geometry_seg.weights = []

            with segm.read_child("WGHT") as wght:
                num_boneweights = wght.read_u32()
                
                for _ in range(num_boneweights):
                    geometry_seg.weights.append((wght.read_u32(), wght.read_f32()))

        elif "CLRL" in next_header:
            geometry_seg.colors = []

            with segm.read_child("CLRL") as clrl:
                num_colors = clrl.read_u32()

                for _ in range(num_colors):
                    geometry_seg.colors += unpack_color(clrl.read_u32())

        elif "UV0L" in next_header:
            with segm.read_child("UV0L") as uv0l:
                num_texcoords = uv0l.read_u32()

                for _ in range(num_texcoords):
                    geometry_seg.texcoords.append(Vector(uv0l.read_f32(2))) 

        elif "NDXL" in next_header:
            with segm.read_child("NDXL") as ndxl:
                num_polygons = ndxl.read_u32()

                for _ in range(num_polygons):
                    polygon = ndxl.read_u16(ndxl.read_u16())
                    geometry_seg.polygons.append(polygon)

        elif "NDXT" in next_header:
            with segm.read_child("NDXT") as ndxt:
                num_tris = ndxt.read_u32()

                for _ in range(num_tris):
                    geometry_seg.triangles.append(ndxt.read_u16(3))

        elif "STRP" in next_header:
            with segm.read_child("STRP") as strp:
                pass

            if segm.read_u16 != 0: #trailing 0 bug
                segm.skip_bytes(-2)

        else:
            with segm.read_child("NULL") as unknown:
                pass

    return geometry_seg



'''


def _write_anm2(anm2: Writer, anim: Animation):

    with anm2.read_child("CYCL") as cycl:
        
        cycl.write_u32(1)
        cycl.write_string(anim.name)
        
        for _ in range(63 - len(anim.name)):
            cycl.write_u8(0)
        
        cycl.write_f32(10.0) #test framerate
        cycl.write_u32(0) #what does play style refer to?
        cycl.write_u32(0, 20) #first frame indices


    with anm2.read_child("KFR3") as kfr3:
        
        kfr3.write_u32(len(anim.bone_transforms.keys()))

        for boneName in anim.bone_transforms.keys():
            kfr3.write_u32(crc(boneName))
            kfr3.write_u32(0) #what is keyframe type?

            kfr3.write_u32(21, 21) #basic testing

            for i, xform in enumerate(anim.bone_transforms[boneName]):
                kfr3.write_u32(i)
                kfr3.write_f32(xform.translation.x, xform.translation.y, xform.translation.z)

            for i, xform in enumerate(anim.bone_transforms[boneName]):
                kfr3.write_u32(i)
                kfr3.write_f32(xform.rotation.x, xform.rotation.y, xform.rotation.z, xform.rotation.w)


'''


