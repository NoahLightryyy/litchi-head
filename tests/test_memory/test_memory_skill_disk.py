"""MasterSkill + SkillDisk 单元测试"""

import pytest
from pydantic import ValidationError

from src.memory.skill_disk import MasterSkill, SkillDisk

# ═══════════════════════════════════════════════════════════════════
# MasterSkill 测试
# ═══════════════════════════════════════════════════════════════════


class TestMasterSkill:
    """MasterSkill Pydantic 模型测试"""

    def test_minimal_skill(self):
        """最小字段创建"""
        skill = MasterSkill(skill_id="test", name="测试大师")
        assert skill.skill_id == "test"
        assert skill.name == "测试大师"
        assert skill.avatar == "🧑‍💼"  # 默认值
        assert skill.tags == []
        assert skill.enabled_by_default is False

    def test_full_skill(self):
        """完整字段创建"""
        skill = MasterSkill(
            skill_id="test",
            name="测试大师",
            avatar="🦸",
            title="测试标题",
            description="测试描述",
            tags=["测试", "demo"],
            system_prompt="你是测试大师",
            knowledge_filter="测试",
            enabled_by_default=True,
        )
        assert skill.skill_id == "test"
        assert skill.name == "测试大师"
        assert skill.avatar == "🦸"
        assert skill.title == "测试标题"
        assert skill.description == "测试描述"
        assert skill.tags == ["测试", "demo"]
        assert skill.system_prompt == "你是测试大师"
        assert skill.knowledge_filter == "测试"
        assert skill.enabled_by_default is True

    def test_frozen_immutable(self):
        """MasterSkill 不可变（frozen=True）"""
        skill = MasterSkill(skill_id="test", name="测试大师")
        with pytest.raises(ValidationError):
            skill.name = "新名字"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════
# SkillDisk 测试
# ═══════════════════════════════════════════════════════════════════


class TestSkillDiskInit:
    """SkillDisk 初始化测试"""

    def test_default_registry_has_7_masters(self):
        """默认注册表有 7 位预置大师"""
        disk = SkillDisk()
        assert disk.available_count == 7

    def test_default_registry_loaded_empty(self):
        """默认加载列表为空"""
        disk = SkillDisk()
        assert disk.loaded_count == 0

    def test_custom_skills(self):
        """注册自定义 skill"""
        custom = MasterSkill(skill_id="custom", name="自定义大师")
        disk = SkillDisk(custom_skills=[custom])
        assert disk.available_count == 8  # 7 预置 + 1 自定义
        assert disk.get("custom") is not None

    def test_available_count_property(self):
        """available_count 属性正确"""
        disk = SkillDisk()
        assert disk.available_count == len(disk.list_available())

    def test_loaded_count_property(self):
        """loaded_count 属性正确"""
        disk = SkillDisk()
        disk.load("buffett")
        assert disk.loaded_count == 1


class TestSkillDiskQuery:
    """SkillDisk 查询方法测试"""

    def test_list_available(self):
        """list_available 返回全部大师"""
        disk = SkillDisk()
        skills = disk.list_available()
        assert len(skills) == 7
        ids = [s.skill_id for s in skills]
        assert "buffett" in ids
        assert "munger" in ids
        assert "graham" in ids

    @pytest.mark.parametrize("skill_id,expected_name", [
        ("buffett", "沃伦·巴菲特"),
        ("munger", "查理·芒格"),
        ("graham", "本杰明·格雷厄姆"),
        ("lynch", "彼得·林奇"),
        ("dalio", "雷·达利欧"),
        ("druckenmiller", "斯坦利·德鲁肯米勒"),
        ("soros", "乔治·索罗斯"),
    ])
    def test_get_returns_correct_skill(self, skill_id, expected_name):
        """get() 按 ID 获取正确大师"""
        disk = SkillDisk()
        skill = disk.get(skill_id)
        assert skill is not None
        assert skill.name == expected_name

    def test_get_nonexistent_returns_none(self):
        """get() 不存在的 skill 返回 None"""
        disk = SkillDisk()
        assert disk.get("nonexistent") is None

    def test_is_loaded_false_initially(self):
        """刚初始化时 is_loaded 返回 False"""
        disk = SkillDisk()
        assert disk.is_loaded("buffett") is False

    def test_is_loaded_after_load(self):
        """加载后 is_loaded 返回 True"""
        disk = SkillDisk()
        disk.load("buffett")
        assert disk.is_loaded("buffett") is True


class TestSkillDiskLoadUnload:
    """SkillDisk 加载/卸载操作测试"""

    def test_load_returns_skill(self):
        """load() 返回 MasterSkill 实例"""
        disk = SkillDisk()
        skill = disk.load("buffett")
        assert isinstance(skill, MasterSkill)
        assert skill.skill_id == "buffett"

    def test_load_adds_to_loaded(self):
        """load() 将 skill 加入加载列表"""
        disk = SkillDisk()
        disk.load("buffett")
        assert "buffett" in [s.skill_id for s in disk.list_loaded()]

    def test_load_nonexistent_raises_keyerror(self):
        """加载不存在的 skill 抛出 KeyError"""
        disk = SkillDisk()
        with pytest.raises(KeyError, match="未找到 Skill"):
            disk.load("nonexistent")

    def test_load_defaults_loads_5(self):
        """load_defaults() 加载 5 位默认开启的大师"""
        disk = SkillDisk()
        loaded = disk.load_defaults()
        assert len(loaded) == 5  # buffett, munger, graham, lynch, dalio
        assert disk.loaded_count == 5

    def test_load_defaults_skips_loaded(self):
        """load_defaults() 不会重复加载已存在的"""
        disk = SkillDisk()
        disk.load("buffett")
        loaded = disk.load_defaults()
        # 5 位默认 - 已加载的 buffett = 4 位新增
        assert len(loaded) == 4

    def test_unload_returns_true(self):
        """成功卸载返回 True"""
        disk = SkillDisk()
        disk.load("buffett")
        assert disk.unload("buffett") is True

    def test_unload_nonexistent_returns_false(self):
        """卸载未加载的 skill 返回 False"""
        disk = SkillDisk()
        assert disk.unload("buffett") is False

    def test_unload_removes_from_loaded(self):
        """卸载后从加载列表移除"""
        disk = SkillDisk()
        disk.load("buffett")
        disk.unload("buffett")
        assert disk.is_loaded("buffett") is False
        assert disk.loaded_count == 0

    def test_reload_all_clears_and_reloads_defaults(self):
        """reload_all() 清空后重新加载默认 skill"""
        disk = SkillDisk()
        disk.load("soros")  # 非默认
        disk.load("buffett")  # 默认
        assert disk.loaded_count == 2

        disk.reload_all()
        assert disk.loaded_count == 5  # 只加载默认
        assert disk.is_loaded("soros") is False  # 非默认已移除
        assert disk.is_loaded("buffett") is True  # 默认还在


class TestSkillDiskRepr:
    """SkillDisk 字符串表示测试"""

    def test_repr(self):
        """__repr__ 包含可用数和已加载数"""
        disk = SkillDisk()
        disk.load("buffett")
        rep = repr(disk)
        assert "available=7" in rep
        assert "loaded=1" in rep

    def test_repr_empty(self):
        """__repr__ 在未加载时也正确"""
        disk = SkillDisk()
        rep = repr(disk)
        assert "available=7" in rep
        assert "loaded=0" in rep
