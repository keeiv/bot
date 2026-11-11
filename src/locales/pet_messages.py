"""English and Traditional Chinese copy for the companion game."""

MESSAGES: dict[str, dict[str, str]] = {
    # ── names ─────────────────────────────────────────────────────────
    "pet.species.fable": {"en": "Fable", "zh": "寓言"},
    "pet.species.ark": {"en": "Ark", "zh": "方舟"},
    "pet.species.nova": {"en": "Nova", "zh": "諾瓦"},
    "pet.about.fable": {
        "en": "A fox that keeps stories. Quick; its strike slips past defences.",
        "zh": "收藏故事的狐。速度快，特技能穿過對手的防禦。",
    },
    "pet.about.ark": {
        "en": "A turtle with a ship on its back. Sturdy; it mends itself in a fight.",
        "zh": "背著船的龜。耐打，戰鬥中會替自己療傷。",
    },
    "pet.about.nova": {
        "en": "A bird hatched from a star. Hits hard, but is easily hurt.",
        "zh": "從星星孵出來的鳥。攻擊最高，但比較不耐打。",
    },
    "pet.form.fable.1": {"en": "Fable", "zh": "寓言"},
    "pet.form.fable.2": {"en": "Fable Chapter", "zh": "寓言・篇章"},
    "pet.form.fable.3": {"en": "Fable Epic", "zh": "寓言・史詩"},
    "pet.form.fable.m": {"en": "Fable Apocrypha", "zh": "寓言・異聞"},
    "pet.form.ark.1": {"en": "Ark", "zh": "方舟"},
    "pet.form.ark.2": {"en": "Ark Voyager", "zh": "方舟・遠航"},
    "pet.form.ark.3": {"en": "Ark Haven", "zh": "方舟・彼岸"},
    "pet.form.ark.m": {"en": "Ghost Ark", "zh": "方舟・幽航"},
    "pet.form.nova.1": {"en": "Nova", "zh": "諾瓦"},
    "pet.form.nova.2": {"en": "Nova Flare", "zh": "諾瓦・耀星"},
    "pet.form.nova.3": {"en": "Supernova", "zh": "諾瓦・超新星"},
    "pet.form.nova.m": {"en": "Dark Nova", "zh": "諾瓦・暗星"},
    "pet.material.stardust_sand": {"en": "Stardust Sand", "zh": "星屑砂"},
    "pet.material.aether_iron": {"en": "Aether Iron Ore", "zh": "以太鐵礦"},
    "pet.material.frostvein_crystal": {"en": "Frostvein Crystal", "zh": "霜紋晶"},
    "pet.material.corona_gold": {"en": "Corona Gold", "zh": "日冕金"},
    "pet.material.streamsilver": {"en": "Streamsilver", "zh": "流光銀"},
    "pet.zone.breeze_meadow": {"en": "Breeze Meadow", "zh": "微風草原"},
    "pet.zone.mistveil_mine": {"en": "Mistveil Mine", "zh": "霧隱礦坑"},
    "pet.zone.frostvein_cavern": {"en": "Frostvein Cavern", "zh": "霜紋冰洞"},
    "pet.zone.corona_ruins": {"en": "Corona Ruins", "zh": "日冕遺跡"},
    "pet.zone.streamsilver_abyss": {"en": "Streamsilver Abyss", "zh": "流光深淵"},
    "pet.nature.brave": {"en": "Brave", "zh": "勇敢"},
    "pet.nature.fierce": {"en": "Fierce", "zh": "兇猛"},
    "pet.nature.bold": {"en": "Bold", "zh": "大膽"},
    "pet.nature.steady": {"en": "Steady", "zh": "沉穩"},
    "pet.nature.patient": {"en": "Patient", "zh": "耐心"},
    "pet.nature.guarded": {"en": "Guarded", "zh": "謹慎"},
    "pet.nature.lively": {"en": "Lively", "zh": "活潑"},
    "pet.nature.nimble": {"en": "Nimble", "zh": "機靈"},
    "pet.nature.restless": {"en": "Restless", "zh": "急躁"},
    "pet.nature.hardy": {"en": "Hardy", "zh": "堅韌"},
    "pet.nature.calm": {"en": "Calm", "zh": "冷靜"},
    "pet.nature.gentle": {"en": "Gentle", "zh": "溫和"},
    "pet.stat.hp": {"en": "HP", "zh": "生命"},
    "pet.stat.atk": {"en": "Attack", "zh": "攻擊"},
    "pet.stat.def": {"en": "Defence", "zh": "防禦"},
    "pet.stat.spd": {"en": "Speed", "zh": "速度"},
    "pet.need.satiety": {"en": "Satiety", "zh": "飽足"},
    "pet.need.mood": {"en": "Mood", "zh": "心情"},
    "pet.need.energy": {"en": "Energy", "zh": "體力"},
    # ── the panel and its card ────────────────────────────────────────
    "pet.button.feed": {"en": "Feed", "zh": "餵食"},
    "pet.button.play": {"en": "Play", "zh": "玩耍"},
    "pet.button.nap": {"en": "Rest", "zh": "休息"},
    "pet.button.collect": {"en": "Collect", "zh": "領取"},
    "pet.button.refresh": {"en": "Refresh", "zh": "重新整理"},
    "pet.button.recall": {"en": "Call it home", "zh": "招回"},
    "pet.not_yours": {
        "en": "This is someone else's companion. Use `/pet panel` for yours.",
        "zh": "這是別人的夥伴。用 `/pet panel` 看你自己的。",
    },
    "pet.card.level": {"en": "Lv {level}", "zh": "Lv {level}"},
    "pet.card.nature": {"en": "{nature} nature", "zh": "性格：{nature}"},
    "pet.card.power": {"en": "Power {power}", "zh": "戰力 {power}"},
    "pet.card.keeper": {"en": "Keeper Lv {level}", "zh": "飼主 Lv {level}"},
    "pet.card.xp": {"en": "Experience", "zh": "經驗"},
    "pet.card.capped": {"en": "Needs a breakthrough", "zh": "需要突破"},
    "pet.card.max": {"en": "Max level", "zh": "已滿級"},
    "pet.card.away": {"en": "Wandered off", "zh": "離家出走"},
    "pet.card.aptitude": {"en": "Aptitude {value}/{cap}", "zh": "天賦 {value}/{cap}"},
    "pet.panel.status": {"en": "Status", "zh": "狀態"},
    "pet.panel.home": {"en": "At home.", "zh": "在家。"},
    "pet.panel.napping": {
        "en": "Resting, up <t:{until}:R>.",
        "zh": "休息中，<t:{until}:R>醒來。",
    },
    "pet.panel.trip": {
        "en": "Exploring **{zone}**, back <t:{until}:R>.",
        "zh": "正在**{zone}**遠征，<t:{until}:R>回來。",
    },
    "pet.panel.trip_done": {
        "en": "Back from **{zone}**. Collect what it found.",
        "zh": "已從**{zone}**回來，可以領取收穫。",
    },
    "pet.panel.away": {
        "en": "It wandered off after thirty days alone. Call it home and it comes back, with everything it had.",
        "zh": "三十天沒人理，牠離家出走了。隨時可以招回，等級與材料都不會少。",
    },
    "pet.panel.sulking": {
        "en": "It is hungry and unhappy, and refuses to go out.",
        "zh": "又餓又不開心，不肯出門。",
    },
    "pet.panel.keeper": {"en": "Keeper", "zh": "飼主"},
    "pet.panel.keeper_value": {
        "en": "Lv {level} ({into}/{needed})\n{coins} coins",
        "zh": "Lv {level}（{into}/{needed}）\n{coins} 金幣",
    },
    "pet.panel.keeper_max": {
        "en": "Lv {level} (max)\n{coins} coins",
        "zh": "Lv {level}（滿級）\n{coins} 金幣",
    },
    "pet.panel.next": {"en": "Next", "zh": "下一步"},
    "pet.panel.next_break": {
        "en": "Breakthrough at Lv {at}: keeper Lv {owner}, {cost}. `/pet breakthrough`",
        "zh": "Lv {at} 突破：飼主 Lv {owner}、{cost}。`/pet breakthrough`",
    },
    "pet.panel.next_level": {
        "en": "{left} experience to Lv {level}.",
        "zh": "距離 Lv {level} 還差 {left} 經驗。",
    },
    "pet.panel.next_none": {"en": "Fully grown.", "zh": "已經完全長成。"},
    "pet.panel.footer": {
        "en": "Needs fall with time. /pet guide explains everything.",
        "zh": "三項數值會隨時間下降。/pet guide 有完整說明。",
    },
    # ── replies ───────────────────────────────────────────────────────
    "pet.adopted": {
        "en": "**{name}** the {species} is yours. Its nature is **{nature}**.",
        "zh": "**{name}**（{species}）成為你的夥伴了，性格是**{nature}**。",
    },
    "pet.recalled": {"en": "**{name}** is home again.", "zh": "**{name}** 回家了。"},
    "pet.renamed": {
        "en": "It answers to **{name}** now.",
        "zh": "現在牠叫 **{name}**。",
    },
    "pet.fed": {"en": "**{name}** ate well.", "zh": "**{name}** 吃飽了。"},
    "pet.played": {"en": "**{name}** had fun.", "zh": "**{name}** 玩得很開心。"},
    "pet.napped": {
        "en": "**{name}** lies down for an hour.",
        "zh": "**{name}** 躺下休息一小時。",
    },
    "pet.level_up": {
        "en": "**{name}** reached Lv {level}.",
        "zh": "**{name}** 升到 Lv {level}。",
    },
    "pet.evolved": {
        "en": "**{name}** evolved into **{form}**.",
        "zh": "**{name}** 進化成 **{form}**。",
    },
    "pet.hit_cap": {
        "en": "It is at its level cap; a breakthrough raises it.",
        "zh": "已到等級上限，突破後才能再升。",
    },
    "pet.keeper_up": {
        "en": "Your keeper level is now {level}.",
        "zh": "飼主等級升到 {level}。",
    },
    "pet.departed": {
        "en": "**{name}** set out for **{zone}**, back <t:{until}:R>.",
        "zh": "**{name}** 出發前往**{zone}**，<t:{until}:R>回來。",
    },
    "pet.collected": {
        "en": "**{name}** is back from **{zone}**.",
        "zh": "**{name}** 從**{zone}**回來了。",
    },
    "pet.found": {"en": "Found", "zh": "收穫"},
    "pet.found_value": {"en": "{coins} coins\n{loot}", "zh": "{coins} 金幣\n{loot}"},
    "pet.found_nothing": {"en": "No materials this time.", "zh": "這次沒有找到材料。"},
    "pet.item": {"en": "{name} x{amount}", "zh": "{name} ×{amount}"},
    "pet.boss_won": {
        "en": "**{name}** beat the guardian of **{zone}** in {rounds} rounds.",
        "zh": "**{name}** 用 {rounds} 回合擊敗了**{zone}**的守護者。",
    },
    "pet.boss_lost": {
        "en": "The guardian of **{zone}** was too strong this time. Try again when **{name}** is stronger.",
        "zh": "**{zone}**的守護者這次太強了，等 **{name}** 再強一點再來。",
    },
    "pet.bag_title": {"en": "{name}'s pack", "zh": "{name} 的背包"},
    "pet.bag_coins": {"en": "Coins", "zh": "金幣"},
    "pet.bag_empty": {"en": "No materials yet.", "zh": "還沒有材料。"},
    "pet.bag_materials": {"en": "Materials", "zh": "材料"},
    "pet.bag_shop": {
        "en": "`/pet shop` sells {items}. The rest is only found on expeditions.",
        "zh": "`/pet shop` 可以買 {items}，其餘只能靠遠征取得。",
    },
    "pet.broke_through": {
        "en": "Breakthrough. **{name}** can now reach Lv {cap}.",
        "zh": "突破成功，**{name}** 的等級上限提高到 Lv {cap}。",
    },
    "pet.broke_through_late": {
        "en": "Breakthrough. **{name}** is now Lv {level}.",
        "zh": "突破成功，**{name}** 升到 Lv {level}。",
    },
    "pet.trained": {
        "en": "**{name}**'s {stat} aptitude is now {value}/{cap}.",
        "zh": "**{name}** 的{stat}天賦提升到 {value}/{cap}。",
    },
    "pet.nature_changed": {
        "en": "**{name}**'s nature changed from {before} to **{after}**. It can change again in seven days.",
        "zh": "**{name}** 的性格從{before}變成**{after}**。七天後才能再次更改。",
    },
    "pet.mutated": {
        "en": "**{name}** mutated into **{form}**.",
        "zh": "**{name}** 突變進化成 **{form}**。",
    },
    "pet.bought": {
        "en": "Bought {item} for {price} coins.",
        "zh": "花 {price} 金幣買了 {item}。",
    },
    "pet.daily": {
        "en": "Day {streak} in a row: {coins} coins.",
        "zh": "連續第 {streak} 天簽到：{coins} 金幣。",
    },
    "pet.duel_title": {"en": "{mine} vs {theirs}", "zh": "{mine} 對 {theirs}"},
    "pet.duel_won": {
        "en": "**{winner}** won in {rounds} rounds, with {left} HP left.",
        "zh": "**{winner}** 在第 {rounds} 回合獲勝，剩下 {left} 生命。",
    },
    "pet.duel_note": {
        "en": "A friendly match: nothing is lost, and {owner}'s companion is unchanged.",
        "zh": "友誼賽：沒有任何損失，{owner} 的夥伴也不受影響。",
    },
    "pet.duel_side": {
        "en": "Lv {level} {form}\nPower {power}",
        "zh": "Lv {level} {form}\n戰力 {power}",
    },
    "pet.rank_title": {"en": "Strongest companions here", "zh": "本伺服器最強的夥伴"},
    "pet.rank_row": {
        "en": "{place}. **{name}** Lv {level} {form}, power {power} ({owner})",
        "zh": "{place}. **{name}** Lv {level} {form}，戰力 {power}（{owner}）",
    },
    "pet.rank_empty": {
        "en": "Nobody here has a companion yet.",
        "zh": "這裡還沒有人領養夥伴。",
    },
    "pet.rank_server_only": {
        "en": "The ranking is per server; use it in one.",
        "zh": "排行榜以伺服器為單位，請在伺服器裡使用。",
    },
    # ── guide ─────────────────────────────────────────────────────────
    "pet.guide.title": {"en": "Companions", "zh": "夥伴"},
    "pet.guide.start": {
        "en": "`/pet adopt` gives you one companion, the same in every server and in DMs. `/pet panel` shows it; the buttons feed it, play with it and let it rest.",
        "zh": "`/pet adopt` 領養一隻夥伴，在每個伺服器和私訊裡都是同一隻。`/pet panel` 開啟面板，按鈕可以餵食、玩耍、休息。",
    },
    "pet.guide.needs_name": {"en": "Needs", "zh": "三項數值"},
    "pet.guide.needs": {
        "en": "Satiety, mood and energy change with time. A well-kept companion brings back more; a hungry, unhappy one refuses to go out. Left alone for thirty days it wanders off, and `/pet recall` always brings it back with nothing lost.",
        "zh": "飽足、心情、體力會隨時間變化。照顧得好，遠征收穫更多；又餓又不開心就不肯出門。三十天沒人理會離家出走，`/pet recall` 隨時能招回，什麼都不會少。",
    },
    "pet.guide.trips_name": {"en": "Expeditions", "zh": "遠征"},
    "pet.guide.trips": {
        "en": "`/pet expedition` sends it out for half an hour, two hours or eight; `/pet collect` takes what it found. New zones open with your keeper level. `/pet boss` fights a zone's guardian once a day.",
        "zh": "`/pet expedition` 派牠出門半小時、兩小時或八小時，`/pet collect` 領取收穫。飼主等級提高會開放新區域。`/pet boss` 每天可以挑戰各區的守護者一次。",
    },
    "pet.guide.growth_name": {"en": "Growing", "zh": "成長"},
    "pet.guide.growth": {
        "en": "Companions run from Lv 2 to 100 and evolve at Lv 30 and 60. Lv 20, 40, 60 and 80 need a breakthrough (`/pet breakthrough`). Past Lv 90 only breakthroughs raise it: keeper Lv 60 and Streamsilver, two levels each, up to 100. `/pet mutate` (Lv 70) is a mutation paid in Streamsilver and Corona Gold.",
        "zh": "夥伴等級是 Lv 2 到 100，Lv 30 與 60 會進化。Lv 20、40、60、80 需要突破（`/pet breakthrough`）。Lv 90 以上只能靠突破：飼主 Lv 60 加流光銀，每次升兩級，直到 100。`/pet mutate`（Lv 70）用流光銀與日冕金突變進化。",
    },
    "pet.guide.nature_name": {"en": "Nature and aptitudes", "zh": "性格與天賦"},
    "pet.guide.nature": {
        "en": "A nature raises the ceiling of one aptitude and lowers another; every nature totals the same. `/pet train` raises an aptitude up to its ceiling. `/pet nature` re-rolls the nature for Corona Gold and Aether Iron Ore, or picks one for two Streamsilver more, once in seven days.",
        "zh": "性格會提高一項天賦的上限、降低另一項，每種性格的總和相同。`/pet train` 把天賦練到上限。`/pet nature` 用日冕金與以太鐵礦隨機更改性格，再加兩個流光銀可以指定，七天內只能改一次。",
    },
    "pet.guide.fair_name": {"en": "Fair play", "zh": "公平"},
    "pet.guide.fair": {
        "en": "Nothing here is bought with money or traded between members. A trip's result is decided when it leaves. Duels (`/pet duel`) are friendly and cost the other side nothing.",
        "zh": "所有東西都不能用錢買，也不能在成員之間交易。遠征結果在出發時就決定了。切磋（`/pet duel`）是友誼賽，對方不會有任何損失。",
    },
    # ── refusals ──────────────────────────────────────────────────────
    "pet.error.no_pet": {
        "en": "You have no companion yet. `/pet adopt` gets you one.",
        "zh": "你還沒有夥伴，用 `/pet adopt` 領養一隻。",
    },
    "pet.error.away": {
        "en": "Your companion wandered off. `/pet recall` brings it home.",
        "zh": "你的夥伴離家出走了，用 `/pet recall` 招回。",
    },
    "pet.error.bad_name": {
        "en": "A name is 1 to 12 characters, without spaces, mentions or formatting marks.",
        "zh": "名字要 1 到 12 個字，不能有空白、提及或格式符號。",
    },
    "pet.error.bad_species": {
        "en": "There is no such species.",
        "zh": "沒有這種夥伴。",
    },
    "pet.error.has_pet": {
        "en": "You already have a companion: one each.",
        "zh": "你已經有夥伴了，每人只能養一隻。",
    },
    "pet.error.not_away": {
        "en": "Your companion is at home.",
        "zh": "你的夥伴好好地在家。",
    },
    "pet.error.no_coins": {
        "en": "That takes {need} coins.",
        "zh": "需要 {need} 金幣。",
    },
    "pet.error.on_trip": {
        "en": "It is on an expedition, back <t:{until}:R>.",
        "zh": "牠正在遠征，<t:{until}:R>回來。",
    },
    "pet.error.napping": {
        "en": "It is resting, up <t:{until}:R>.",
        "zh": "牠正在休息，<t:{until}:R>醒來。",
    },
    "pet.error.too_soon": {
        "en": "Not yet: again <t:{until}:R>.",
        "zh": "還不行，<t:{until}:R>才能再來一次。",
    },
    "pet.error.full": {"en": "It is not hungry.", "zh": "牠還不餓。"},
    "pet.error.tired": {
        "en": "It is too tired. Let it rest.",
        "zh": "牠太累了，讓牠休息一下。",
    },
    "pet.error.rested": {"en": "It is not tired.", "zh": "牠還不累。"},
    "pet.error.daily_done": {
        "en": "You already checked in today.",
        "zh": "今天已經簽到過了。",
    },
    "pet.error.bad_zone": {"en": "There is no such zone.", "zh": "沒有這個區域。"},
    "pet.error.zone_locked": {
        "en": "That zone opens at keeper Lv {need}.",
        "zh": "這個區域要飼主 Lv {need} 才開放。",
    },
    "pet.error.sulking": {
        "en": "It is hungry and unhappy, and refuses to go. Feed it and play with it first.",
        "zh": "牠又餓又不開心，不肯出門。先餵食、陪牠玩。",
    },
    "pet.error.bad_trip": {
        "en": "Choose one of the listed durations.",
        "zh": "請選擇列出的時間。",
    },
    "pet.error.no_trip": {"en": "It is not on an expedition.", "zh": "牠沒有在遠征。"},
    "pet.error.boss_done": {
        "en": "You already beat this guardian today.",
        "zh": "今天已經打敗過這個守護者了。",
    },
    "pet.error.max_level": {"en": "It is already Lv 100.", "zh": "已經 Lv 100 了。"},
    "pet.error.level_low": {
        "en": "That needs your companion at Lv {need}.",
        "zh": "夥伴要到 Lv {need} 才行。",
    },
    "pet.error.owner_low": {
        "en": "That needs keeper Lv {need}.",
        "zh": "飼主等級要到 Lv {need} 才行。",
    },
    "pet.error.short": {
        "en": "Not enough materials. Missing: {need}.",
        "zh": "材料不夠，還缺：{need}。",
    },
    "pet.error.bad_stat": {"en": "There is no such aptitude.", "zh": "沒有這項天賦。"},
    "pet.error.aptitude_max": {
        "en": "This nature's ceiling for it is {cap}, and it is there.",
        "zh": "這個性格在這項天賦的上限是 {cap}，已經到頂了。",
    },
    "pet.error.bad_nature": {"en": "There is no such nature.", "zh": "沒有這種性格。"},
    "pet.error.same_nature": {
        "en": "It already has that nature.",
        "zh": "牠現在就是這個性格。",
    },
    "pet.error.nature_cooldown": {
        "en": "Its nature can change again <t:{until}:R>.",
        "zh": "性格要到<t:{until}:R>才能再次更改。",
    },
    "pet.error.mutated": {"en": "It has already mutated.", "zh": "牠已經突變過了。"},
    "pet.error.bad_purchase": {
        "en": "Buy 1 to 99 of something the shop sells.",
        "zh": "只能購買商店有賣的材料，一次 1 到 99 個。",
    },
    "pet.error.duel_self": {
        "en": "Pick another member's companion.",
        "zh": "請選擇其他成員的夥伴。",
    },
    "pet.error.duel_no_pet": {
        "en": "That member has no companion.",
        "zh": "對方還沒有夥伴。",
    },
    "pet.error.duel_away": {
        "en": "That member's companion has wandered off.",
        "zh": "對方的夥伴離家出走了。",
    },
    "pet.error.storage": {
        "en": "Your companion could not be reached just now. Nothing changed; try again in a moment.",
        "zh": "暫時讀不到你的夥伴資料，什麼都沒有變動，請稍後再試。",
    },
    # ── achievements ──────────────────────────────────────────────────
    "achievement.pet_adopt.name": {"en": "First meeting", "zh": "初次相遇"},
    "achievement.pet_adopt.description": {
        "en": "Adopt your first companion",
        "zh": "領養第一隻夥伴",
    },
    "achievement.pet_final_form.name": {"en": "Final form", "zh": "最終型態"},
    "achievement.pet_final_form.description": {
        "en": "Evolve a companion to its third stage",
        "zh": "夥伴進化到第三階段",
    },
    "achievement.pet_mutation.name": {"en": "Mutation", "zh": "異變"},
    "achievement.pet_mutation.description": {
        "en": "Mutate a companion",
        "zh": "讓夥伴突變進化",
    },
    "achievement.pet_max_level.name": {"en": "To the top together", "zh": "並肩到頂"},
    "achievement.pet_max_level.description": {
        "en": "Raise a companion to Lv 100",
        "zh": "夥伴達到 Lv 100",
    },
}
