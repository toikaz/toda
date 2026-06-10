import socket
import threading
import time
import json
import math
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = 5555
TICK_RATE = 30
TICK_TIME = 1.0 / TICK_RATE

connections = {}
server_socket = None

class GameServer:
    def __init__(self):
        self.state = "LOBBY"
        self.lobby_players = {}
        self.players = {}
        self.towers = {}
        self.creeps = {}
        self.tower_last_attack = {}
        self.creep_counter = 0
        self.wave_timer = 0.0
        self.passive_gold_timer = 0.0
        self.fountain_timer = 0.0
        self.neutral_timer = 0.0
        self.game_time = 0.0
        self.gold_events = []
        
        self.item_db = {
            "Claws": {"atk": 10, "cost": 50},
            "Ring of Health": {"hp_regen": 6.0, "cost": 116},
            "Void Stone": {"mp_regen": 1.5, "cost": 250}, 
            "Gauntlets": {"max_hp": 50, "hp_regen": 1.2, "cost": 50},
            "Slippers": {"atk": 5, "spd": 0.5, "cost": 50},
            "Mantle": {"max_mp": 50, "mp_regen": 0.5, "cost": 50}, 
            "Ogre Axe": {"max_hp": 500, "atk": 15, "cost": 333},
            "Blade": {"atk": 15, "spd": 1.5, "cost": 333},
            "Staff": {"max_mp": 250, "atk": 15, "cost": 333},
            "Boots": {"spd": 3.5, "cost": 400},
            "Broadsword": {"atk": 50, "cost": 500}
        }
        self.reset_game()

    def reset_game(self):
        self.players.clear()
        self.towers.clear()
        self.creeps.clear()
        self.tower_last_attack.clear()
        self.creep_counter = 0
        self.wave_timer = 0.0
        self.passive_gold_timer = 0.0
        self.fountain_timer = 0.0
        self.neutral_timer = 0.0
        self.game_time = 0.0
        self.gold_events.clear()
        self.setup_map_objects()
        self.spawn_neutrals()

    def setup_map_objects(self):
        self.towers["T1_TOP1"] = {"id": "T1_TOP1", "team": 1, "x": -24.0, "y": 0.0,   "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T1_TOP2"] = {"id": "T1_TOP2", "team": 1, "x": -24.0, "y": 15.0,  "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T1_MID1"] = {"id": "T1_MID1", "team": 1, "x": -4.0,  "y": -4.0,  "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T1_MID2"] = {"id": "T1_MID2", "team": 1, "x": -12.0, "y": -12.0, "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T1_BOT1"] = {"id": "T1_BOT1", "team": 1, "x": 0.0,   "y": -24.0, "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T1_BOT2"] = {"id": "T1_BOT2", "team": 1, "x": 15.0,  "y": -24.0, "hp": 2200, "max_hp": 2200, "type": "tower"}

        self.towers["T2_TOP1"] = {"id": "T2_TOP1", "team": 2, "x": 0.0,   "y": 24.0,  "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T2_TOP2"] = {"id": "T2_TOP2", "team": 2, "x": -15.0, "y": 24.0,  "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T2_MID1"] = {"id": "T2_MID1", "team": 2, "x": 4.0,   "y": 4.0,   "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T2_MID2"] = {"id": "T2_MID2", "team": 2, "x": 12.0,  "y": 12.0,  "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T2_BOT1"] = {"id": "T2_BOT1", "team": 2, "x": 24.0,  "y": 0.0,   "hp": 2200, "max_hp": 2200, "type": "tower"}
        self.towers["T2_BOT2"] = {"id": "T2_BOT2", "team": 2, "x": 24.0,  "y": -15.0, "hp": 2200, "max_hp": 2200, "type": "tower"}
        for t_id in self.towers:
            self.tower_last_attack[t_id] = 0.0

    def spawn_neutrals(self):
        camps = [
            {"id": "camp_1", "x": -6.0, "y": -18.0},
            {"id": "camp_2", "x": -16.0, "y": 3.0},
            {"id": "camp_3", "x": 6.0, "y": 18.0},
            {"id": "camp_4", "x": 12.0, "y": -1.0}
        ]
        for camp in camps:
            n_id = f"neutral_{camp['id']}"
            if n_id not in self.creeps:
                self.creeps[n_id] = {
                    "id": n_id, "team": 0, "type": "neutral", "line": "camp",
                    "x": camp["x"], "y": camp["y"], "spawn_x": camp["x"], "spawn_y": camp["y"],
                    "hp": 700, "max_hp": 700,
                    "attack": 25, "speed": 4.5, "target_id": None, "last_attack_time": 0.0
                }

    def spawn_creep_wave(self):
        lines = ["top", "mid", "bot"]
        r_spawn = (-25.0, -25.0)
        d_spawn = (25.0, 25.0)
        for line in lines:
            rc_id = f"creep_1_{self.creep_counter}"
            self.creeps[rc_id] = {
                "id": rc_id, "team": 1, "type": "creep", "line": line,
                "x": r_spawn[0], "y": r_spawn[1], "hp": 550, "max_hp": 550,
                "attack": 21, "speed": 6.0, "target_id": None, "last_attack_time": 0.0
            }
            self.creep_counter += 1
            dc_id = f"creep_2_{self.creep_counter}"
            self.creeps[dc_id] = {
                "id": dc_id, "team": 2, "type": "creep", "line": line,
                "x": d_spawn[0], "y": d_spawn[1], "hp": 550, "max_hp": 550,
                "attack": 21, "speed": 6.0, "target_id": None, "last_attack_time": 0.0
            }
            self.creep_counter += 1

    def add_player(self, conn_id, hero_type, preferred_team):
        team = preferred_team
        start_x = -25.0 if team == 1 else 25.0
        start_y = -25.0 if team == 1 else 25.0
        stats = {
            "warrior": {"hp": 750, "mp": 160, "atk": 48, "spd": 3.7},
            "mage":    {"hp": 480, "mp": 380, "atk": 62, "spd": 3.9},
            "hunter":  {"hp": 580, "mp": 220, "atk": 54, "spd": 4.2}
        }.get(hero_type, {"hp": 600, "mp": 200, "atk": 50, "spd": 10.0})

        self.players[conn_id] = {
            "id": conn_id, "team": team, "hero": hero_type, "type": "hero",
            "x": start_x, "y": start_y, "heading": 0.0,
            "target_x": start_x, "target_y": start_y,
            "hp": stats["hp"], "max_hp": stats["hp"],
            "base_max_hp": stats["hp"],
            "mp": stats["mp"], "max_mp": stats["mp"],
            "base_max_mp": stats["mp"],
            "level": 1, "gold": 200, "networth": 200, 
            "base_attack": stats["atk"], "base_speed": stats["spd"],
            "attack": stats["atk"], "speed": stats["spd"],
            "inventory": [], "target_id": None,
            "cooldowns": {"q": 0.0, "w": 0.0},
            "buffs": {"battle_cry": 0.0, "windrun": 0.0},
            "last_attack_time": 0.0, "status": "idle",
            "respawn_time": 0.0, "hp_regen": 2.0, "mp_regen": 1.0
        }

    def start_match(self):
        self.state = "MATCH"
        self.reset_game()
        team_assign = 1
        for cid, pdata in self.lobby_players.items():
            t = 1 if team_assign <= 3 else 2
            try:
                pdata["conn"].sendall((json.dumps({"action": "start_match", "team": t}) + "\n").encode())
            except:
                pass
            team_assign += 1
        self.lobby_players.clear()

    def remove_player(self, conn_id):
        if conn_id in self.players: del self.players[conn_id]

    def get_closest_enemy_by_priority(self, unit, radius=5.0):
        best_target = None
        best_priority = 4 
        min_dist = radius
        for c_id, c in self.creeps.items():
            if c["team"] != unit["team"] and c["hp"] > 0:
                d = math.hypot(c["x"] - unit["x"], c["y"] - unit["y"])
                if d < min_dist:
                    best_target = c_id; best_priority = 1; min_dist = d
        if best_priority > 1:
            for t_id, t in self.towers.items():
                if t["team"] != unit["team"] and t["hp"] > 0:
                    d = math.hypot(t["x"] - unit["x"], t["y"] - unit["y"])
                    if d < min_dist:
                        best_target = t_id; best_priority = 2; min_dist = d
        if best_priority > 2:
            for p_id, p in self.players.items():
                if p["team"] != unit["team"] and p["hp"] > 0 and p["respawn_time"] <= 0:
                    d = math.hypot(p["x"] - unit["x"], p["y"] - unit["y"])
                    if d < min_dist:
                        best_target = p_id; best_priority = 3; min_dist = d
        return best_target

    def process_kill_reward(self, attacker_id, target):
        if attacker_id in self.players:
            p = self.players[attacker_id]
            if target["type"] == "creep": reward = 15
            elif target["type"] == "neutral": reward = 45
            else: reward = 116
            p["gold"] += reward
            p["networth"] += reward
            self.gold_events.append({
                "player_id": attacker_id, "amount": reward,
                "x": p["x"], "y": p["y"], "timestamp": time.time()
            })

    def update(self, dt):
        if self.state != "MATCH":
            return
            
        self.game_time += dt
        radiant_towers = sum(1 for t in self.towers.values() if t["team"] == 1 and t["hp"] > 0)
        dire_towers = sum(1 for t in self.towers.values() if t["team"] == 2 and t["hp"] > 0)

        if radiant_towers == 0 or dire_towers == 0:
            for cid, conn in list(connections.items()):
                try: conn.close()
                except: pass
            connections.clear()
            self.state = "LOBBY"
            self.reset_game()
            return

        current_time = time.time()
        self.gold_events = [e for e in self.gold_events if current_time - e["timestamp"] < 0.5]
        
        self.passive_gold_timer += dt
        add_gold = False
        if self.passive_gold_timer >= 6.0:
            self.passive_gold_timer = 0.0
            add_gold = True

        for p in self.players.values():
            if p["respawn_time"] <= 0:
                if add_gold:
                    p["gold"] += 1
                    p["networth"] += 1
                for buff in list(p["buffs"]):
                    if p["buffs"][buff] > 0:
                        p["buffs"][buff] = max(0, p["buffs"][buff] - dt)
                bonus_max_hp = 0
                bonus_max_mp = 0
                bonus_atk = 0
                bonus_spd = 0
                bonus_hp_reg = 0
                bonus_mp_reg = 0
                for item in p["inventory"]:
                    i_data = self.item_db.get(item, {})
                    bonus_max_hp += i_data.get("max_hp", 0)
                    bonus_max_mp += i_data.get("max_mp", 0)
                    bonus_atk += i_data.get("atk", 0)
                    bonus_spd += i_data.get("spd", 0)
                    bonus_hp_reg += i_data.get("hp_regen", 0)
                    bonus_mp_reg += i_data.get("mp_regen", 0)
                p["max_hp"] = p["base_max_hp"] + bonus_max_hp
                p["max_mp"] = p["base_max_mp"] + bonus_max_mp
                if p["buffs"]["battle_cry"] > 0: 
                    bonus_atk += 20
                    bonus_spd += 4.0
                p["attack"] = p["base_attack"] + bonus_atk
                p["speed"] = p["base_speed"] + bonus_spd
                if p["buffs"]["windrun"] > 0: p["speed"] *= 2.0 
                p["hp"] = min(p["max_hp"], p["hp"] + (p["hp_regen"] + bonus_hp_reg) * dt)
                p["mp"] = min(p["max_mp"], p["mp"] + (p["mp_regen"] + bonus_mp_reg) * dt)

        self.fountain_timer += dt
        if self.fountain_timer >= 1.0:
            self.fountain_timer = 0.0
            fountains = {1: (-25.0, -25.0), 2: (25.0, 25.0)}
            for p in self.players.values():
                if p["respawn_time"] > 0: continue
                my_f_x, my_f_y = fountains[p["team"]]
                if math.hypot(p["x"] - my_f_x, p["y"] - my_f_y) <= 6.0:
                    p["hp"] = min(p["max_hp"], p["hp"] + 100)
                    p["mp"] = min(p["max_mp"], p["mp"] + 50)
                opp_team = 2 if p["team"] == 1 else 1
                opp_f_x, opp_f_y = fountains[opp_team]
                if math.hypot(p["x"] - opp_f_x, p["y"] - opp_f_y) <= 6.0:
                    p["hp"] = max(0, p["hp"] - 300)
                    if p["hp"] <= 0:
                        p["respawn_time"] = 5.0 + (p["networth"] // 200)

        self.wave_timer += dt
        if self.wave_timer >= 30.0 or (len([c for c in self.creeps.values() if c["type"] == "creep"]) == 0 and self.wave_timer > 5.0):
            self.spawn_creep_wave()
            self.wave_timer = 0.0

        self.neutral_timer += dt
        if self.neutral_timer >= 60.0:
            self.spawn_neutrals()
            self.neutral_timer = 0.0

        for p in self.players.values():
            if p["respawn_time"] > 0:
                p["respawn_time"] = max(0, p["respawn_time"] - dt)
                if p["respawn_time"] == 0:
                    p["x"] = -25.0 if p["team"] == 1 else 25.0
                    p["y"] = -25.0 if p["team"] == 1 else 25.0
                    p["target_x"], p["target_y"] = p["x"], p["y"]
                    p["hp"] = p["max_hp"]
                    p["mp"] = p["max_mp"]
                    p["status"] = "idle"

        for t_id, t in self.towers.items():
            if t["hp"] <= 0: continue
            if current_time - self.tower_last_attack[t_id] >= 1.5:
                target = None
                for c in self.creeps.values():
                    if c["team"] != t["team"] and c["hp"] > 0 and math.hypot(c["x"] - t["x"], c["y"] - t["y"]) <= 5.0:
                        target = c; break
                if not target:
                    for p in self.players.values():
                        if p["team"] != t["team"] and p["hp"] > 0 and p["respawn_time"] <= 0 and math.hypot(p["x"] - t["x"], p["y"] - t["y"]) <= 5.0:
                            target = p; break
                if target:
                    target["hp"] = max(0, target["hp"] - 70)
                    self.tower_last_attack[t_id] = current_time
                    if target["hp"] <= 0 and target.get("type") == "hero":
                        target["respawn_time"] = 5.0 + (target["networth"] // 200)

        for c_id, c in list(self.creeps.items()):
            if c["hp"] <= 0:
                del self.creeps[c_id]; continue
            tid = self.get_closest_enemy_by_priority(c, radius=5.0)
            c["target_id"] = tid
            target_obj = None
            if tid: target_obj = self.creeps.get(tid) or self.towers.get(tid) or self.players.get(tid)
            if c["type"] == "neutral" and target_obj:
                dist_from_spawn = math.hypot(c["spawn_x"] - c["x"], c["spawn_y"] - c["y"])
                if dist_from_spawn > 10.0:
                    target_obj = None
                    c["target_id"] = None
            if target_obj and target_obj["hp"] > 0:
                dx, dy = target_obj["x"] - c["x"], target_obj["y"] - c["y"]
                dist = math.hypot(dx, dy)
                if dist <= 1.5:
                    if current_time - c["last_attack_time"] >= 1.2:
                        target_obj["hp"] = max(0, target_obj["hp"] - c["attack"])
                        c["last_attack_time"] = current_time
                        if target_obj["hp"] <= 0 and target_obj.get("type") == "hero":
                            target_obj["respawn_time"] = 5.0 + (target_obj["networth"] // 200)
                else:
                    c["x"] += (dx / dist) * c["speed"] * dt
                    c["y"] += (dy / dist) * c["speed"] * dt
            else:
                if c["type"] == "neutral":
                    dx, dy = c["spawn_x"] - c["x"], c["spawn_y"] - c["y"]
                    dist = math.hypot(dx, dy)
                    if dist > 0.1:
                        c["x"] += (dx / dist) * c["speed"] * dt
                        c["y"] += (dy / dist) * c["speed"] * dt
                    else:
                        c["hp"] = min(c["max_hp"], c["hp"] + 20.0 * dt)
                else:
                    dest_x = 25.0 if c["team"] == 1 else -25.0
                    dest_y = 25.0 if c["team"] == 1 else -25.0
                    if c["line"] == "top": pivot_x, pivot_y = (-23.0, 23.0) if c["team"] == 1 else (23.0, -23.0)
                    elif c["line"] == "bot": pivot_x, pivot_y = (23.0, -23.0) if c["team"] == 1 else (-23.0, 23.0)
                    else: pivot_x, pivot_y = dest_x, dest_y

                    should_pivot = False
                    if c["line"] == "top": should_pivot = (c["team"] == 1 and c["y"] < 20.0) or (c["team"] == 2 and c["y"] > -20.0)
                    elif c["line"] == "bot": should_pivot = (c["team"] == 1 and c["x"] < 20.0) or (c["team"] == 2 and c["x"] > -20.0)

                    if should_pivot: tx, ty = pivot_x, pivot_y
                    else: tx, ty = dest_x, dest_y

                    dx, dy = tx - c["x"], ty - c["y"]
                    dist = math.hypot(dx, dy)
                    if dist > 0.1:
                        c["x"] += (dx / dist) * c["speed"] * dt
                        c["y"] += (dy / dist) * c["speed"] * dt

        for p_id, p in self.players.items():
            if p["respawn_time"] > 0: continue
            for spell in p["cooldowns"]:
                if p["cooldowns"][spell] > 0:
                    p["cooldowns"][spell] = max(0, p["cooldowns"][spell] - dt)

            dx, dy = p["target_x"] - p["x"], p["target_y"] - p["y"]
            dist = math.hypot(dx, dy)
            if dist > 0.1:
                p["status"] = "moving"
                p["heading"] = math.degrees(math.atan2(dy, dx)) - 90.0
                move_dist = p["speed"] * dt
                if move_dist >= dist: p["x"], p["y"] = p["target_x"], p["target_y"]
                else:
                    p["x"] += (dx / dist) * move_dist
                    p["y"] += (dy / dist) * move_dist
            else:
                if p["status"] == "moving": p["status"] = "idle"

            if p["target_id"]:
                target = self.players.get(p["target_id"]) or self.towers.get(p["target_id"]) or self.creeps.get(p["target_id"])
                if target and target["hp"] > 0:
                    tdx, tdy = target["x"] - p["x"], target["y"] - p["y"]
                    dist_to_target = math.hypot(tdx, tdy)
                    p["heading"] = math.degrees(math.atan2(tdy, tdx)) - 90.0
                    if dist_to_target <= 3.5:
                        p["target_x"], p["target_y"] = p["x"], p["y"]
                        if current_time - p["last_attack_time"] >= 1.2:
                            target["hp"] = max(0, target["hp"] - p["attack"])
                            p["last_attack_time"] = current_time
                            if target["hp"] <= 0:
                                self.process_kill_reward(p_id, target)
                                p["target_id"] = None
                                if target.get("type") == "hero": target["respawn_time"] = 5.0 + (target["networth"] // 200)
                    else:
                        p["target_x"], p["target_y"] = target["x"], target["y"]

    def handle_command(self, conn_id, cmd):
        p = self.players.get(conn_id)
        if not p or p["respawn_time"] > 0: return

        action = cmd.get("action")
        if action == "move":
            p["target_x"], p["target_y"] = cmd["x"], cmd["y"]
            p["target_id"] = None
        elif action == "attack_unit":
            tid = cmd.get("target_id")
            target = self.players.get(tid) or self.towers.get(tid) or self.creeps.get(tid)
            if target and target["team"] != p["team"]: p["target_id"] = tid
            else: p["target_id"] = None

        elif action == "cast_q":
            if p["cooldowns"]["q"] <= 0:
                if p["hero"] == "warrior" and p["mp"] >= 70:
                    tid = cmd.get("target_id")
                    target = self.players.get(tid) or self.towers.get(tid) or self.creeps.get(tid)
                    if target and target["team"] != p["team"] and target["hp"] > 0:
                        p["mp"] -= 70; p["cooldowns"]["q"] = 8.0
                        target["hp"] = max(0, target["hp"] - 130)
                        if target["hp"] <= 0: self.process_kill_reward(conn_id, target)
                elif p["hero"] == "mage" and p["mp"] >= 80:
                    p["mp"] -= 80; p["cooldowns"]["q"] = 6.0
                    tx, ty = cmd.get("x", 0), cmd.get("y", 0)
                    for enemy in list(self.players.values()) + list(self.creeps.values()) + list(self.towers.values()):
                        if enemy["team"] != p["team"] and enemy["hp"] > 0:
                            if math.hypot(enemy["x"] - tx, enemy["y"] - ty) <= 4.0:
                                enemy["hp"] = max(0, enemy["hp"] - 110)
                                if enemy["hp"] <= 0: self.process_kill_reward(conn_id, enemy)
                elif p["hero"] == "hunter" and p["mp"] >= 60:
                    tid = cmd.get("target_id")
                    target = self.players.get(tid) or self.towers.get(tid) or self.creeps.get(tid)
                    if target and target["team"] != p["team"] and target["hp"] > 0:
                        if math.hypot(target["x"] - p["x"], target["y"] - p["y"]) <= 14.0:
                            p["mp"] -= 60; p["cooldowns"]["q"] = 5.0
                            target["hp"] = max(0, target["hp"] - 150)
                            if target["hp"] <= 0: self.process_kill_reward(conn_id, target)

        elif action == "cast_w":
            if p["cooldowns"]["w"] <= 0:
                if p["hero"] == "warrior" and p["mp"] >= 50:
                    p["mp"] -= 50; p["cooldowns"]["w"] = 15.0
                    p["buffs"]["battle_cry"] = 5.0
                elif p["hero"] == "mage" and p["mp"] >= 120:
                    p["mp"] -= 120; p["cooldowns"]["w"] = 12.0
                    tx, ty = cmd.get("x", 0), cmd.get("y", 0)
                    for enemy in list(self.players.values()) + list(self.creeps.values()) + list(self.towers.values()):
                        if enemy["team"] != p["team"] and enemy["hp"] > 0:
                            if math.hypot(enemy["x"] - tx, enemy["y"] - ty) <= 7.0:
                                enemy["hp"] = max(0, enemy["hp"] - 180)
                                if enemy["hp"] <= 0: self.process_kill_reward(conn_id, enemy)
                elif p["hero"] == "hunter" and p["mp"] >= 40:
                    p["mp"] -= 40; p["cooldowns"]["w"] = 10.0
                    p["buffs"]["windrun"] = 4.0

        elif action == "buy_item":
            item = cmd.get("item", "Claws")
            shop_x = -25.0 if p["team"] == 1 else 25.0
            shop_y = -25.0 if p["team"] == 1 else 25.0
            if math.hypot(p["x"] - shop_x, p["y"] - shop_y) > 6.0: return
            cost = self.item_db.get(item, {}).get("cost", 9999)
            if p["gold"] >= cost and len(p["inventory"]) < 6:
                p["gold"] -= cost
                p["inventory"].append(item)

        elif action == "sell_item":
            slot = cmd.get("slot") 
            shop_x = -25.0 if p["team"] == 1 else 25.0
            shop_y = -25.0 if p["team"] == 1 else 25.0
            if math.hypot(p["x"] - shop_x, p["y"] - shop_y) > 6.0: return
            if isinstance(slot, int) and 0 <= slot < len(p["inventory"]):
                item_name = p["inventory"].pop(slot) 
                cost = self.item_db.get(item_name, {}).get("cost", 0)
                refund = cost // 2
                p["gold"] += refund
                p["networth"] -= refund

    def get_team_serialized_state(self, team):
        vision_sources = []
        for p in self.players.values():
            if p["team"] == team and p.get("respawn_time", 0) <= 0:
                vision_sources.append((p["x"], p["y"], 8.0))
        for t in self.towers.values():
            if t["team"] == team and t["hp"] > 0:
                vision_sources.append((t["x"], t["y"], 6.0))
        for c in self.creeps.values():
            if c["team"] == team and c["hp"] > 0 and c.get("type") == "creep":
                vision_sources.append((c["x"], c["y"], 4.0))

        def is_visible(obj):
            if obj.get("type") == "tower": return True
            if obj.get("team") == team: return True
            ox, oy = obj["x"], obj["y"]
            for vx, vy, vrad in vision_sources:
                if math.hypot(ox - vx, oy - vy) <= vrad: return True
            return False

        filtered_players = [p for p in self.players.values() if is_visible(p)]
        filtered_towers = [t for t in self.towers.values() if is_visible(t)]
        
        filtered_creeps = []
        for c in self.creeps.values():
            if c.get("type") == "creep" and is_visible(c):
                filtered_creeps.append(c)
        
        camps = [
            {"id": "camp_1", "x": -6.0, "y": -18.0},
            {"id": "camp_2", "x": -16.0, "y": 3.0},
            {"id": "camp_3", "x": 6.0, "y": 18.0},
            {"id": "camp_4", "x": 12.0, "y": -1.0}
        ]
        
        for camp in camps:
            n_id = f"neutral_{camp['id']}"
            cx, cy = camp["x"], camp["y"]
            in_vision = False
            for vx, vy, vrad in vision_sources:
                if math.hypot(cx - vx, cy - vy) <= vrad:
                    in_vision = True; break
            if in_vision:
                if n_id in self.creeps and self.creeps[n_id]["hp"] > 0:
                    filtered_creeps.append(self.creeps[n_id])
            else:
                filtered_creeps.append({
                    "id": n_id, "team": 0, "type": "neutral", "line": "camp",
                    "x": cx, "y": cy, "hp": 700, "max_hp": 700
                })

        filtered_gold_events = []
        for e in self.gold_events:
            p_obj = self.players.get(e["player_id"])
            if p_obj and is_visible(p_obj):
                filtered_gold_events.append(e)

        return json.dumps({
            "game_time": self.game_time,
            "players": filtered_players,
            "towers": filtered_towers,
            "creeps": filtered_creeps,
            "gold_events": filtered_gold_events
        })

def client_handler(game_server, conn, addr):
    conn_id = f"player_{addr[1]}"
    try:
        init_data = conn.recv(1024).decode('utf-8')
        if not init_data: return
        params = json.loads(init_data)
        
        if params.get("client_type") == "launcher":
            if game_server.state != "LOBBY":
                conn.close()
                return
            game_server.lobby_players[conn_id] = {"hero": params.get("hero", "warrior"), "conn": conn}
            if len(game_server.lobby_players) >= 6:
                game_server.start_match()
            while game_server.state == "LOBBY" and conn_id in game_server.lobby_players:
                time.sleep(1)
            return

        game_server.add_player(conn_id, params.get("hero", "warrior"), int(params.get("team", 1)))
        connections[conn_id] = conn
        
        buffer = ""
        while game_server.state == "MATCH":
            data = conn.recv(1024).decode('utf-8')
            if not data: break
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                cmd = json.loads(line)
                game_server.handle_command(conn_id, cmd)
    except Exception: pass
    finally:
        if conn_id in game_server.lobby_players: del game_server.lobby_players[conn_id]
        game_server.remove_player(conn_id)
        if conn_id in connections: del connections[conn_id]
        conn.close()

def main():
    global server_socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"MOBA Server v6 (Lobby + TUI + Autoritative) running on {HOST}:{PORT}")
    
    game_server = GameServer()
    
    def game_loop():
        last_time = time.time()
        while True:
            now = time.time()
            dt = now - last_time
            if dt < TICK_TIME:
                time.sleep(TICK_TIME - dt); continue
            last_time = now
            game_server.update(dt)

    threading.Thread(target=game_loop, daemon=True).start()
    
    def net_server():
        while True:
            try:
                conn, addr = server_socket.accept()
                threading.Thread(target=client_handler, args=(game_server, conn, addr), daemon=True).start()
            except:
                break 

    threading.Thread(target=net_server, daemon=True).start()

    while True:
        time.sleep(TICK_TIME)
        if game_server.state == "LOBBY":
            state_str = json.dumps({
                "action": "lobby_update", 
                "count": len(game_server.lobby_players),
                "players": [{"hero": p["hero"]} for p in game_server.lobby_players.values()]
            }) + "\n"
            dead_lobby = []
            for cid, pdata in game_server.lobby_players.items():
                try: pdata["conn"].sendall(state_str.encode('utf-8'))
                except: dead_lobby.append(cid)
            for cid in dead_lobby: del game_server.lobby_players[cid]
            
        elif game_server.state == "MATCH":
            dead_conns = []
            for cid, conn in list(connections.items()):
                try:
                    player = game_server.players.get(cid)
                    if player:
                        state_str = game_server.get_team_serialized_state(player["team"]) + "\n"
                        conn.sendall(state_str.encode('utf-8'))
                except:
                    dead_conns.append(cid)
            for cid in dead_conns:
                if cid in connections: del connections[cid]

if __name__ == "__main__":
    main()