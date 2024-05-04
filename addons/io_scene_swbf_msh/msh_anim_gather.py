""" Converts currently active Action to an msh Animation """

import bpy
import math
from enum import Enum
from typing import List, Set, Dict, Tuple
from itertools import zip_longest
from .msh_model import *
from .msh_model_utilities import *
from .msh_utilities import *
from .msh_model_gather import *

from .msh_skeleton_utilities import *

from .crc import to_crc


'''
Convert the active Action into an Animation.  When exported SWBF anims, there is the issue
that all bones in the anim must be in the skeleton/basepose anim.  We guarantee this by
only keying bones if they are in the armature's preserved skeleton (swbf_msh_skel) and 
adding dummy frames if the bones are not in the armature.

If a preserved skeleton is not present, we include only the keyed bones and add dummy frames for
the root (root_name)
'''

def extract_anim(armature: bpy.types.Armature, root_name: str) -> Animation:

    if not armature.animation_data or not armature.animation_data.action:
        raise RuntimeError("Cannot export animation data without an active Action on armature!")

    action = armature.animation_data.action


    # Set of bones to include in SKL2/animation stuff
    keyable_bones = get_real_BONES(armature)

    # If it doesn't have a preserved skeleton, then we add the scene root. 
    # If it does have a preserved skeleton, any objects not animatable by blender (i.e. objects above the skeleton, scene root)
    # will be included in the preserved skeleton 
    if len(armature.data.swbf_msh_skel):
        keyable_bones.add(root_name)

    # Subset of above bones to key with dummy frames (all bones not in armature)
    dummy_bones = set([keyable_bone for keyable_bone in keyable_bones if keyable_bone not in armature.data.bones])


    anim = Animation();

    root_crc = to_crc(root_name)

    if not action:
        framerange = Vector((0.0,1.0))
    else:
        framerange = action.frame_range
    
    num_frames = math.floor(framerange.y - framerange.x) + 1
    increment  = (framerange.y - framerange.x) / (num_frames - 1)

    anim.end_index = num_frames - 1
    

    for keyable_bone in keyable_bones:
        anim.bone_frames[to_crc(keyable_bone)] = ([], [])


    for frame in range(num_frames):
        
        frame_time = int(framerange.x + frame * increment)
        bpy.context.scene.frame_set(frame_time)

        for keyable_bone in keyable_bones:

            bone_crc = to_crc(keyable_bone)

            if keyable_bone in dummy_bones:

                rframe = RotationFrame(frame, convert_rotation_space(Quaternion()))
                tframe = TranslationFrame(frame, Vector((0.0,0.0,0.0)))

            else:

                bone = armature.pose.bones[keyable_bone]

                transform = bone.matrix

                if bone.parent:
                    transform = bone.parent.matrix.inverted() @ transform
     
                loc, rot, _ = transform.decompose()

                rframe = RotationFrame(frame, convert_rotation_space(rot))
                tframe = TranslationFrame(frame, convert_vector_space(loc))

            anim.bone_frames[bone_crc][0].append(tframe)
            anim.bone_frames[bone_crc][1].append(rframe)


    return anim
