"""English and Traditional Chinese copy for russian_roulette."""

MESSAGES: dict[str, dict[str, str]] = {
    "russian_roulette.pull_trigger": {"en": "Pull trigger", "zh": "扣動扳機"},
    "russian_roulette.check_whether_the_next_chamber_contains": {
        "en": "Check whether the next chamber contains a bullet",
        "zh": "偷看彈巢中的下一發是否為子彈",
    },
    "russian_roulette.spin_the_cylinder_again_to_move": {
        "en": "Spin the cylinder again to move the bullet",
        "zh": "強制重新旋轉彈巢，改變子彈位置",
    },
    "russian_roulette.halve_the_damage_if_the_next": {
        "en": "Halve the damage if the next shot contains a bullet",
        "zh": "若下一發是子彈，傷害減半",
    },
    "russian_roulette.force_the_opponent_to_take_this": {
        "en": "Force the opponent to take this shot instead",
        "zh": "強制對手替你開這一槍",
    },
    "russian_roulette.double_the_damage_for_this_round": {
        "en": "Double the damage for this round",
        "zh": "這局擊中金額翻倍",
    },
    "russian_roulette.unknown_item": {"en": "Unknown item", "zh": "未知道具"},
    "russian_roulette.game_invite_red_and_black_roulette": {
        "en": "[Game invite] Red and Black Roulette",
        "zh": "[遊戲邀請] 極限籌碼：紅黑左輪",
    },
    "russian_roulette.invites_to_russian_roulette_rules_starting": {
        "en": "{v0} invites {v1} to Russian Roulette\n\nRules:\n• Starting balance: 5000 CT\n• 5 rounds\n• One bullet is placed randomly each round\n• A hit costs 1500 CT (2000 CT after three empty shots)\n• Each player receives three random items",
        "zh": "{v0} 邀請 {v1} 進行俄羅斯輪盤遊戲\n\n遊戲規則：\n• 初始資產：5,000 CT\n• 總局數：5 局\n• 每局隨機放入 1 顆子彈\n• 中彈扣除 1,500 CT（連續空槍3次後增至 2,000 CT）\n• 每人隨機獲得 3 個道具",
    },
    "russian_roulette.game_started_red_and_black_roulette": {
        "en": "[Game started] Red and Black Roulette",
        "zh": "[遊戲開始] 極限籌碼：紅黑左輪",
    },
    "russian_roulette.game_started_takes_the_first_turn": {
        "en": "Game started! {v0} takes the first turn",
        "zh": "遊戲開始！{v0} 先手",
    },
    "russian_roulette.items_choose_an_item": {
        "en": "[Items] Choose an item",
        "zh": "[道具] 選擇要使用的道具",
    },
    "russian_roulette.choose_an_item_to_use": {
        "en": "Choose an item to use",
        "zh": "選擇一個道具來使用",
    },
    "russian_roulette.round_red_and_black_roulette": {
        "en": "[Round {v0}] Red and Black Roulette",
        "zh": "[第 {v0} 局] 極限籌碼：紅黑左輪",
    },
    "russian_roulette.current_player": {
        "en": "Current player: {v0}",
        "zh": "當前玩家：{v0}",
    },
    "russian_roulette.cylinder_status": {"en": "Cylinder status", "zh": "彈巢狀態"},
    "russian_roulette.current_chamber_6_empty_shots": {
        "en": "Current chamber: {v0}/6\nEmpty shots: {v1}",
        "zh": "當前位置: {v0}/6\n空槍次數: {v1}",
    },
    "russian_roulette.winner": {"en": "Winner", "zh": "勝利者"},
    "russian_roulette.final_ct": {"en": "Final CT: {v0}", "zh": "最終 CT: {v0}"},
    "russian_roulette.bullet": {"en": "Bullet", "zh": "子彈"},
    "russian_roulette.empty_chamber": {"en": "Empty chamber", "zh": "空槍"},
    "russian_roulette.it_is_another_player_s_turn": {
        "en": "It is another player's turn",
        "zh": "不是你的回合",
    },
    "russian_roulette.hit_round_result": {
        "en": "[Hit] Round result",
        "zh": "[中彈] 遊戲結束",
    },
    "russian_roulette.pulls_the_trigger_bang_ct_lost": {
        "en": "{v0} pulls the trigger… bang!\n{v1} CT lost",
        "zh": "{v0} 扣動扳機...砰！\n扣除 {v1} CT",
    },
    "russian_roulette.empty_shot_safe": {
        "en": "[Empty shot] Safe",
        "zh": "[空槍] 安全通過",
    },
    "russian_roulette.pulls_the_trigger_click_safe_this": {
        "en": "{v0} pulls the trigger… click!\nSafe this time",
        "zh": "{v0} 扣動扳機...咔嚓！\n安全通過",
    },
    "russian_roulette.special_status": {"en": "Special status", "zh": "特殊狀態"},
    "russian_roulette.double_stakes_active": {
        "en": "Double stakes active",
        "zh": "加倍賭注已啟動",
    },
    "russian_roulette.this_item_is_not_in_the": {
        "en": "This item is not in the inventory",
        "zh": "你沒有這個道具",
    },
    "russian_roulette.x_ray_glasses_peek_result": {
        "en": "[X-ray glasses] Peek result",
        "zh": "[透視眼鏡] 偷看結果",
    },
    "russian_roulette.next_chamber": {
        "en": "Next chamber: {v0}",
        "zh": "下一發是：{v0}",
    },
    "russian_roulette.fate_shuffle_cylinder_spun": {
        "en": "[Fate shuffle] Cylinder spun",
        "zh": "[命運洗牌] 重新洗牌",
    },
    "russian_roulette.the_cylinder_was_spun_again_and": {
        "en": "The cylinder was spun again and the bullet moved",
        "zh": "彈巢已重新洗牌，子彈位置改變",
    },
    "russian_roulette.blank_round_ready": {
        "en": "[Blank round] Ready",
        "zh": "[空包彈] 已準備",
    },
    "russian_roulette.damage_is_halved_if_the_next": {
        "en": "Damage is halved if the next chamber contains a bullet",
        "zh": "若下一發是子彈，傷害將減半",
    },
    "russian_roulette.blank_round_active": {
        "en": "Blank round active",
        "zh": "空包彈已啟用",
    },
    "russian_roulette.redirect_shot_transferred": {
        "en": "[Redirect] Shot transferred",
        "zh": "[強制轉向] 轉移開槍",
    },
    "russian_roulette.must_take_this_shot_instead": {
        "en": "{v0} must take this shot instead",
        "zh": "強制 {v0} 替你開這一槍",
    },
    "russian_roulette.this_item_can_only_be_used": {
        "en": "This item can only be used once per game",
        "zh": "此道具每場遊戲限用一次",
    },
    "russian_roulette.double_stakes_active_36fac1": {
        "en": "[Double stakes] Active",
        "zh": "[加倍賭注] 已啟動",
    },
    "russian_roulette.a_hit_this_round_costs_double": {
        "en": "A hit this round costs double CT",
        "zh": "這局擊中金額將翻倍",
    },
}
