import logging
from pathlib import Path
from typing import List, Optional, Union

import bpy
from bpy.types import AdjustmentSequence, AnyType, Context

from kiritanify.types import ImageSequence, KiritanifyScriptSequence, SoundSequence
from kiritanify.utils import _datetime_str, _sequences_all, hash_text, trim_bracketed_sentence

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _enum_chara_names(_: AnyType, context: Context):
  gs = _global_setting(context)
  return [
    (c.chara_name, c.chara_name, '')
    for c in gs.characters
  ]


class CaptionStyle(bpy.types.PropertyGroup):
  name = 'kiritanify.caption_style'

  fill_color: bpy.props.FloatVectorProperty(
    name='Fill', subtype='COLOR_GAMMA',
    size=4, default=(1., 1., 1., 1.),
    min=0., max=1.,
  )
  stroke_color: bpy.props.FloatVectorProperty(
    name='Stroke', subtype='COLOR_GAMMA',
    size=4, default=(0., 0., 0., 1.),
    min=0., max=1.,
  )
  stroke_width: bpy.props.FloatProperty(name="Stroke width", default=8)

  font_path: bpy.props.StringProperty(
    name='Font path',
    default='/usr/share/fonts/TTF/mplus-1p-regular.ttf',
  )
  font_size: bpy.props.IntProperty(name='Font size', default=42)
  max_height_px: bpy.props.IntProperty(name='Caption height px', default=256)

  def is_equal(self, style: 'CaptionStyle') -> bool:
    return (
        self.fill_color == style.fill_color
        and self.stroke_color == style.stroke_color
    )

  def update(self, style: 'CaptionStyle'):
    self.fill_color = style.fill_color
    self.stroke_color = style.stroke_color
    self.stroke_width = style.stroke_width


class TachieStyle(bpy.types.PropertyGroup):
  name = "kiritanify.tachie_style"

  offset_x_px: bpy.props.FloatProperty(name='Offset x')
  offset_y_px: bpy.props.FloatProperty(name='Offset y')
  use_flip_x: bpy.props.BoolProperty(name='Flip x', default=False)  # a.k.a mirror x

  def is_equal(self, style: 'TachieStyle') -> bool:
    return (
        self.offset_x_px == style.offset_x_px
        and self.offset_y_px == style.offset_y_px
        and self.use_flip_x == style.use_flip_x
    )

  def update(self, style: 'TachieStyle'):
    self.offset_x_px = style.offset_x_px
    self.offset_y_px = style.offset_y_px
    self.use_flip_x = style.use_flip_x


class VoiceStyle(bpy.types.PropertyGroup):
  name = 'kiritanify.voice_style'

  volume: bpy.props.FloatProperty(name="Volume", min=0, max=2.0, default=1)
  speed: bpy.props.FloatProperty(name="Speed", min=0.5, max=4.0, default=1)
  pitch: bpy.props.FloatProperty(name="Pitch", min=0.5, max=2.0, default=1)
  intonation: bpy.props.FloatProperty(name="Intonation", min=0, max=2.0, default=1)

  def is_equal(self, style: 'VoiceStyle') -> bool:
    return (
        self.volume == style.volume
        and self.speed == style.speed
        and self.pitch == style.pitch
        and self.intonation == style.intonation
    )

  def update(self, style: 'VoiceStyle'):
    self.volume = style.volume
    self.speed = style.speed
    self.pitch = style.pitch
    self.intonation = style.intonation


class ICacheState:
  def invalidate(self) -> None:
    raise NotImplementedError

  def update(
      self,
      context: Context,
      chara: 'KiritanifyCharacterSetting',
      seq: KiritanifyScriptSequence,
  ) -> None:
    raise NotImplementedError

  def is_changed(self, context, chara: 'KiritanifyCharacterSetting', seq: KiritanifyScriptSequence) -> bool:
    raise NotImplementedError


class CaptionCacheState(bpy.types.PropertyGroup, ICacheState):
  name = "kiritanify.caption_cache_state"

  invalid: bpy.props.BoolProperty(name='invalid', default=True)

  text: bpy.props.StringProperty(name='text')
  style: bpy.props.PointerProperty(type=CaptionStyle, name='style')

  def invalidate(self) -> None:
    self.ivnalid = True

  def update(
      self,
      global_setting: 'KiritanifyGlobalSetting',
      chara: 'KiritanifyCharacterSetting',
      seq: KiritanifyScriptSequence,
  ) -> None:
    _setting = _script_setting(seq)
    text = _setting.caption_text()
    style = _setting.caption_style(global_setting, chara)
    self.invalid = False
    self.text = text
    self.style.update(style)

  def is_changed(
      self,
      global_setting: 'KiritanifyGlobalSetting',
      chara: 'KiritanifyCharacterSetting',
      seq: KiritanifyScriptSequence,
  ) -> bool:
    if self.invalid:
      return True

    _setting = _script_setting(seq)
    text = _setting.caption_text()
    style = _setting.caption_style(global_setting, chara)
    return not (
        self.style.is_equal(style)
        and self.text == text
    )


class VoiceCacheState(bpy.types.PropertyGroup, ICacheState):
  name = 'kiritanify.voice_cache_state'

  invalid: bpy.props.BoolProperty(name='invalid', default=True)

  text: bpy.props.StringProperty(name='text')
  style: bpy.props.PointerProperty(type=VoiceStyle, name='style')

  def invalidate(self) -> None:
    self.invalid = True

  def update(
      self,
      global_setting: 'KiritanifyGlobalSetting',
      chara: 'KiritanifyCharacterSetting',
      seq: KiritanifyScriptSequence,
  ) -> None:
    _setting = _script_setting(seq)
    text = _setting.voice_text()
    style = _setting.voice_style(global_setting, chara)
    self.invalid = False
    self.text = text
    self.style.update(style)

  def is_changed(
      self,
      global_setting: 'KiritanifyGlobalSetting',
      chara: 'KiritanifyCharacterSetting',
      seq: KiritanifyScriptSequence,
  ) -> bool:
    if self.invalid:
      return True

    _setting = _script_setting(seq)
    text = _setting.voice_text()
    style = _setting.voice_style(global_setting, chara)

    return not (
        self.style.is_equal(style)
        and self.text == text
    )


class KiritanifyCacheSetting(bpy.types.PropertyGroup):
  name = 'kiritanify.cache_dir_setting'

  def voice_path(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifyScriptSequence) -> Path:
    ss = _script_setting(seq)
    dir_path = self._gen_dir('caption', chara)
    return dir_path / f'{_datetime_str()}:{hash_text(ss.voice_text())}.png'

  def caption_path(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifyScriptSequence) -> Path:
    ss = _script_setting(seq)
    dir_path = self._gen_dir('caption', chara)
    return dir_path / f'{_datetime_str()}:{hash_text(ss.caption_text())}.png'

  def root_dir(self) -> Path:
    return Path(bpy.path.abspath('//kiritanify'))

  def _gen_dir(self, data_type: str, chara: 'KiritanifyCharacterSetting') -> Path:
    abspath = bpy.path.abspath(f'//kiritanify/{data_type}/{chara.chara_name}')
    path = Path(abspath)
    path.mkdir(parents=True, exist_ok=True)
    return path


class KiritanifyScriptSequenceSetting(bpy.types.PropertyGroup):
  name = 'kiritanify.script_sequence_setting'

  text: bpy.props.StringProperty(name='text')

  gen_voice: bpy.props.BoolProperty(name='gen voice', default=True)
  gen_caption: bpy.props.BoolProperty(name='gen caption', default=True)

  # custom
  use_custom_voice_text: bpy.props.BoolProperty(name='use custom voice text', default=False)
  custom_voice_text: bpy.props.StringProperty(name='custom voice text')
  use_custom_voice_style: bpy.props.BoolProperty(name='use custom voice style', default=False)
  custom_voice_style: bpy.props.PointerProperty(type=VoiceStyle, name='custom voice style')
  use_custom_caption_style: bpy.props.BoolProperty(name='use custom property', default=False)
  custom_caption_style: bpy.props.PointerProperty(type=CaptionStyle, name='caption style')

  # seq reference
  voice_seq_name: bpy.props.StringProperty(name='Voice seq name')
  caption_seq_name: bpy.props.StringProperty(name='Caption seq name')

  # cache
  voice_cache_state: bpy.props.PointerProperty(name='voice cache state', type=VoiceCacheState)
  caption_cache_state: bpy.props.PointerProperty(name='caption cache state', type=CaptionCacheState)

  def voice_text(self) -> str:
    script = self.raw_voice_text().strip()
    return trim_bracketed_sentence(script.replace('\\n', ''))

  def raw_voice_text(self) -> str:
    if self.use_custom_voice_text:
      return self.custom_voice_text
    return self.text

  def voice_style(
      self,
      global_setting: 'KiritanifyGlobalSetting',
      chara: 'KiritanifyCharacterSetting',
  ) -> VoiceStyle:
    if self.use_custom_voice_style:
      return self.custom_voice_style
    return chara.voice_style

  def caption_text(self) -> str:
    return self.text.replace('\\n', '\n')

  def caption_style(
      self,
      global_setting: 'KiritanifyGlobalSetting',
      chara: 'KiritanifyCharacterSetting',
  ) -> CaptionStyle:
    if self.use_custom_caption_style:
      return self.custom_caption_style
    return chara.caption_style

  def find_voice_seq(self, context: Context) -> Optional[SoundSequence]:
    if self.voice_seq_name == '' or self.voice_seq_name not in _sequences_all(context):
      return None
    return _sequences_all(context)[self.voice_seq_name]

  def find_caption_seq(self, context: Context) -> Optional[ImageSequence]:
    if self.caption_seq_name == '' or self.caption_seq_name not in _sequences_all(context):
      return None
    return _sequences_all(context)[self.caption_seq_name]


class KiritanifyCharacterSetting(bpy.types.PropertyGroup):
  name = 'kiritanify.character_setting'

  chara_name: bpy.props.StringProperty(name='Name')
  cid: bpy.props.IntProperty(name='cid', min=0)

  caption_style: bpy.props.PointerProperty(name='Caption style', type=CaptionStyle)
  tachie_style: bpy.props.PointerProperty(name='Tachie style', type=TachieStyle)
  voice_style: bpy.props.PointerProperty(name='Voice style', type=VoiceStyle)

  tachie_directory: bpy.props.StringProperty(name='Tachie dir', subtype='DIR_PATH', default='')

  def __repr__(self):
    return f'<KiritanifyCharacterSetting chara_name={self.chara_name} cid={self.cid}>'

  def caption_channel(
      self,
      global_setting: 'KiritanifyGlobalSetting',
  ) -> int:
    idx = global_setting.character_index(self)
    return global_setting.start_channel_for_caption + 1 * idx

  def script_channel(
      self,
      global_setting: 'KiritanifyGlobalSetting',
  ) -> int:
    idx = global_setting.character_index(self)
    return global_setting.start_channel_for_script + 2 * idx + 0

  def voice_channel(
      self,
      global_setting: 'KiritanifyGlobalSetting',
  ) -> int:
    idx = global_setting.character_index(self)
    return global_setting.start_channel_for_script + 2 * idx + 1

  def tachie_channel(
      self,
      global_setting: 'KiritanifyGlobalSetting',
  ) -> int:
    idx = global_setting.character_index(self)
    return global_setting.start_channel_for_tachie + 2 * idx + 1

  def tachie_files(self) -> List[Path]:
    if self.tachie_directory == '':
      logger.debug(f'tachie directory: empty string')
      return []
    dir_path = Path(bpy.path.abspath(self.tachie_directory)).resolve()
    if not dir_path.exists():
      logger.debug(f'tachie directory not found: {dir_path}')
      return []
    return [
      child
      for child in dir_path.iterdir()
      if child.is_file()
    ]


class SeikaCenterSetting(bpy.types.PropertyGroup):
  name = "kiritanify.seika_center_setting"

  addr: bpy.props.StringProperty(name='Addr', default='http://192.168.88.7:7180')
  user: bpy.props.StringProperty(name='User', default='SeikaServerUser')
  password: bpy.props.StringProperty(name='Password', default='SeikaServerPassword')


def _get_character_enum_items(scene, context):
  kiritanify: 'KiritanifyGlobalSetting' = context.scene.kiritanify
  result = [
    (c.chara_name, c.chara_name, "")
    for c in kiritanify.characters  # type: KiritanifyCharacterSetting
  ]
  return result


class KiritanifyGlobalSetting(bpy.types.PropertyGroup):
  name = "kiritanify.global_setting"

  seika_center: bpy.props.PointerProperty(type=SeikaCenterSetting)

  start_channel_for_script: bpy.props.IntProperty('Script start channel', min=1, default=10)
  start_channel_for_caption: bpy.props.IntProperty('Script start channel', min=1, default=30)
  start_channel_for_tachie: bpy.props.IntProperty('Script start channel', min=1, default=20)
  characters: bpy.props.CollectionProperty(type=KiritanifyCharacterSetting)

  cache_setting: bpy.props.PointerProperty(type=KiritanifyCacheSetting, name='cache setting')

  new_script_chara_name: bpy.props.EnumProperty(items=_get_character_enum_items, name='new chara name')

  def character_index(
      self,
      chara: KiritanifyCharacterSetting,
  ) -> int:
    for _idx, _chara in enumerate(self.characters):
      if chara == _chara:
        return _idx
    raise ValueError(f'Unexpected character: {chara!r}')

  def find_character_by_name(self, chara_name: str) -> Optional[KiritanifyCharacterSetting]:
    for c in self.characters:
      if c.chara_name == chara_name:
        return c
    return None


PROPGROUP_CLASSES = [
  CaptionStyle,
  TachieStyle,
  VoiceStyle,
  CaptionCacheState,
  VoiceCacheState,
  SeikaCenterSetting,
  KiritanifyCacheSetting,
  KiritanifyScriptSequenceSetting,
  KiritanifyCharacterSetting,
  KiritanifyGlobalSetting,
]


def _global_setting(context: Context) -> KiritanifyGlobalSetting:
  return context.scene.kiritanify


def _script_setting(seq: KiritanifyScriptSequence) -> KiritanifyScriptSequenceSetting:
  return seq.kiritanify_script


def get_selected_script_sequence(context: Context) -> Optional[KiritanifyScriptSequence]:
  global_setting = _global_setting(context)
  channels = set([
    chara.script_channel(global_setting)
    for chara in global_setting.characters  # type: KiritanifyCharacterSetting
  ])
  for seq in context.selected_sequences:  # type: Union[Sequence, ImageSequence]
    if not isinstance(seq, AdjustmentSequence):
      continue
    if not seq.channel in channels:
      continue
    return seq
