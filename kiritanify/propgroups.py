from pathlib import Path

import bpy

from .types import KiritanifySequence
from .utils import _datetime_str, _seq_setting


class CaptionStyle(bpy.types.PropertyGroup):
  name = "kiritanify.caption_style"

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
  name = "kiritanify.voice_style"

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

  def update(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> None:
    raise NotImplementedError

  def is_changed(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> bool:
    raise NotImplementedError


class CaptionCacheState(bpy.types.PropertyGroup, ICacheState):
  name = "kiritanify.caption_cache_state"

  invalid: bpy.props.BoolProperty(name='invalid', default=True)

  text: bpy.props.StringProperty(name='text')
  style: bpy.props.PointerProperty(type=CaptionStyle, name='style')

  def invalidate(self) -> None:
    self.ivnalid = True

  def update(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> None:
    _setting = _seq_setting(seq)
    text = _setting.caption_text()
    style = _setting.caption_style(chara)
    self.invalid = False
    self.text = text
    self.style.update(style)

  def is_changed(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> bool:
    if self.invalid:
      return True

    _setting = _seq_setting(seq)
    text = _setting.caption_text()
    style = _setting.caption_style(chara)
    return not (
        self.style.is_equal(style)
        and self.text == text
    )


class TachieCacheState(bpy.types.PropertyGroup, ICacheState):
  name = "kiritanify.tachie_cache_state"

  invalid: bpy.props.BoolProperty(name='invalid', default=True)

  tachie_name: bpy.props.StringProperty(name='tachie name')
  style: bpy.props.PointerProperty(type=TachieStyle, name='style')

  def invalidate(self) -> None:
    self.ivnalid = True

  def update(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> None:
    self.invalid = False

    _setting = _seq_setting(seq)
    name = _setting.tachie_name(chara)
    style = _setting.tachie_style(chara)

    self.tachie_name = name
    self.style.update(style)

  def is_changed(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> bool:
    if self.invalid:
      return True

    _setting = _seq_setting(seq)
    name = _setting.tachie_name(chara)
    style = _setting.tachie_style(chara)
    return (
        self.tachie_name == name
        and self.style.is_equal(style)
    )


class VoiceCacheState(bpy.types.PropertyGroup, ICacheState):
  name = "kiritanify.voice_cache_state"

  invalid: bpy.props.BoolProperty(name='invalid', default=True)

  text: bpy.props.StringProperty(name='text')
  style: bpy.props.PointerProperty(type=VoiceStyle, name='style')

  def invalidate(self) -> None:
    self.invalid = True

  def update(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> None:
    _setting = _seq_setting(seq)
    text = _setting.voice_text()
    style = _setting.voice_style(chara)
    self.invalid = False
    self.text = text
    self.style.update(style)

  def is_changed(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> bool:
    if self.invalid:
      return True

    _setting = _seq_setting(seq)
    text = _setting.voice_text()
    style = _setting.voice_style(chara)

    return not (
        self.style.is_equal(style)
        and self.text == text
    )


class KiritanifyCacheSetting(bpy.types.PropertyGroup):
  name = "kiritanify.cache_dir_setting"

  def voice_path(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> Path:
    dir_path = self._gen_dir('voice', chara)
    return dir_path / f'{_datetime_str()}.ogg'

  def caption_path(self, chara: 'KiritanifyCharacterSetting', seq: KiritanifySequence) -> Path:
    dir_path = self._gen_dir('caption', chara)
    return dir_path / f'{_datetime_str()}.png'

  def _gen_dir(self, data_type: str, chara: 'KiritanifyCharacterSetting') -> Path:
    abspath = bpy.path.abspath(f"//{data_type}/{chara.chara_name}")
    path = Path(abspath)
    path.mkdir(exist_ok=True)
    return path


class KiritanifySequenceSetting(bpy.types.PropertyGroup):
  name = "kiritanify.sequence_setting"

  text: bpy.props.StringProperty(name='text')

  def voice_text(self) -> str:
    # TODO:
    pass

  def voice_style(self, chara: 'KiritanifyCharacterSetting') -> VoiceStyle:
    # TODO:
    pass

  def caption_text(self) -> str:
    # TODO:
    pass

  def caption_style(self, chara: 'KiritanifyCharacterSetting') -> CaptionStyle:
    # TODO: 
    pass

  def tachie_name(self, chara: 'KiritanifyCharacterSetting') -> str:
    # TODO: 
    pass

  def tachie_style(self, chara: 'KiritanifyCharacterSetting') -> TachieStyle:
    # TODO: 
    pass


class KiritanifyCharacterSetting(bpy.types.PropertyGroup):
  name = "kiritanify.character_setting"

  chara_name: bpy.props.StringProperty(name="Name")
  cid: bpy.props.IntProperty(name="cid", min=0)

  caption_style: bpy.props.PointerProperty(name="Caption style", type=CaptionStyle)
  tachie_style: bpy.props.PointerProperty(name="Tachie style", type=TachieStyle)
  voice_style: bpy.props.PointerProperty(name="Voice style", type=VoiceStyle)


class KiritanifyGlobalSetting(bpy.types.PropertyGroup):
  name = "kiritanify.global_setting"

  characters: bpy.props.CollectionProperty(type=KiritanifyCharacterSetting)


CLASSES = [
  CaptionStyle,
  TachieStyle,
  VoiceStyle,
  CaptionCacheState,
  TachieCacheState,
  VoiceCacheState,
  KiritanifyCacheSetting,
  KiritanifySequenceSetting,
  KiritanifyCharacterSetting,
  KiritanifyGlobalSetting,
]
