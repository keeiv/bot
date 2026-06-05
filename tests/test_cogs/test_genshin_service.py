"""GenshinService 單元測試"""

import os
from src.services.genshin_service import GenshinService


def test_encryption_decryption():
    service = GenshinService()
    test_cookie = "ltoken=abc123xyz; ltuid=987654321;"
    
    encrypted = service.encrypt_cookie(test_cookie)
    assert encrypted != test_cookie
    
    decrypted = service.decrypt_cookie(encrypted)
    assert decrypted == test_cookie


def test_map_game_biz():
    service = GenshinService()
    assert service._map_game_biz_to_str("hk4e_cn") == "genshin"
    assert service._map_game_biz_to_str("hk4e_global") == "genshin"
    assert service._map_game_biz_to_str("hkrpg_cn") == "starrail"
    assert service._map_game_biz_to_str("hkrpg_global") == "starrail"
    assert service._map_game_biz_to_str("nap_cn") == "zzz"
    assert service._map_game_biz_to_str("nap_global") == "zzz"
    assert service._map_game_biz_to_str("bh3_cn") == "honkai"
    assert service._map_game_biz_to_str("bh3_global") == "honkai"
    assert service._map_game_biz_to_str("unknown_game") == "unknown"


def test_to_traditional_chinese():
    from src.services.genshin_service import to_traditional_chinese
    
    assert to_traditional_chinese("混沌回忆") == "混沌回憶"
    assert to_traditional_chinese("虚构叙事") == "虛構敘事"
    assert to_traditional_chinese("值日行动其十二") == "值日行動其十二"
    assert to_traditional_chinese("造象立说其四") == "造像立說其四"
    assert to_traditional_chinese("偶像螟蝗·难度04") == "偶像螟蝗·難度04"
    assert to_traditional_chinese("当前赛季") == "當前賽季"
