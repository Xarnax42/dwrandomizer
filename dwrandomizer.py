#!/usr/bin/env python3

import argparse
import random
import sys
import hashlib
from worldmap import WorldMap

VERSION = "0.9.4"
#sha1sums of various roms
prg0sums = ['6a50ce57097332393e0e8751924fd56456ef083c', #Dragon Warrior (U) (PRG0) [!].nes
            '66330df6fe3e3c85adb8183721e5f88c149e52eb', #Dragon Warrior (U) (PRG0) [b1].nes
            '49974889619f1d8c39b6c20fa208c62a0a73ecce', #Dragon Warrior (U) (PRG0) [b1][o1].nes
            'd98b8a3fc93bb2f1f5016326556b68998dd5f85d', #Dragon Warrior (U) (PRG0) [b2].nes
            'e81a693efe322be9584c97b55c6d7ae38ae44a66', #Dragon Warrior (U) (PRG0) [o1].nes
            '6e1a52b7b3a13494536bbab7248690861665001a', #Dragon Warrior (U) (PRG0) [o2].nes
            '3077d5bd5c5c3744398b122d5ee1bba7055c8d45'] #Dragon Warrior (U) (PRG0) [o3].nes
prg1sums = ['1ecc63aaac50a9612eaa8b69143858c3e48dd0ae'] #Dragon Warrior (U) (PRG1) [!].nes

class Rom:
  # Slices for various data. Offsets include iNES header.
  chest_content_slice = slice(0x5de0, 0x5e59, 4)
  enemy_stats_slice = slice(0x5e5b, 0x60db)
  warps_slice = slice(0xf3d8, 0xf50b)
  zones_slice = slice(0xf55f, 0xf5c3)
  mp_req_slice = slice(0x1d63, 0x1d6d) #mp requirements for each spell
  player_stats_slice = slice(0x60dd, 0x6191)
  weapon_shop_inv_slice = slice(0x19a1, 0x19cc)
  new_spell_slice = slice(0xeaf9, 0xeb1f, 4)
  chests_slice = slice(0x5ddd, 0x5e59)

  token_slice = slice(0xe11e, 0xe12b, 6)
  flute_slice = slice(0xe15d, 0xe16a, 6)
  armor_slice = slice(0xe173, 0xe180, 6)

  def __init__(self, filename):
    input_file = open(filename, 'rb')
    self.rom_data = bytearray(input_file.read())
    self.owmap = WorldMap()
    self.owmap.from_rom_data(self.rom_data)
    input_file.close()
    self.enemy_stats = self.rom_data[self.enemy_stats_slice]
    self.mp_reqs = self.rom_data[self.mp_req_slice]
    self.zones = self.rom_data[self.zones_slice]
    self.shop_inventory = self.rom_data[self.weapon_shop_inv_slice]
    self.token_loc = self.rom_data[self.token_slice]
    self.flute_loc = self.rom_data[self.flute_slice]
    self.armor_loc = self.rom_data[self.armor_slice]
    self.player_stats = self.rom_data[self.player_stats_slice]
    self.new_spell_levels = self.rom_data[self.new_spell_slice]
    self.chests = self.rom_data[self.chests_slice]

  def sha1(self):
    """
    Returns a sha1 checksum of the rom data
    """
    return hashlib.sha1(self.rom_data).hexdigest()

  def verify_checksum(self):
    digest = self.sha1()
    if digest in prg0sums:
      return 0
    elif digest in prg1sums:
      return 1
    return False

  def shuffle_chests(self):
    """
    Shuffles the contents of all chests in the game. Checks are used to ensure no
    quest items are located in Charlock chests.
    """
    chest_contents = self.chests[3::4]
    for i in range(len(chest_contents)):
      # change all gold (and erdrick's tablet) to large gold stash
      if (chest_contents[i] >= 18 and chest_contents[i] <= 20):
        chest_contents[i] = 21
      # 50/50 chance to have erdrick's token in a chest
      if chest_contents[i] == 23:
        if random.randint(0,1):
          self.rom_data[self.token_slice.start] = 0 # remove token from swamp
          chest_contents[i] = 10 # put it in a chest
        else:
          chest_contents[i] = 21

    random.shuffle(chest_contents)

    # make sure required quest items aren't in Charlock
    charlock_chests = chest_contents[11:17] + chest_contents[24:25]
    charlock_chest_indices = (11, 12, 13, 14, 15, 16, 24)
    quest_items = (10, 13, 15, 16)
    for item in quest_items:
      if (item in charlock_chests):
        for i in charlock_chest_indices:
          if chest_contents[i] == item:
            # this could probably be cleaner...
            j = self.non_charlock_chest()
            while chest_contents[j] in quest_items:
              j = self.non_charlock_chest()
            chest_contents[j], chest_contents[i] = chest_contents[i], chest_contents[j]

    # make sure there's a key to in the throne room
    if not (3 in chest_contents[4:7]):
      for i in range(len(chest_contents)):
        if chest_contents[i] == 3:
          j = random.randint(4, 6)
          # if key is in charlock and chest[j] contains a quest item, try again
          while (i in charlock_chest_indices and (chest_contents[j] in quest_items)):
            j = random.randint(4, 6)
          chest_contents[j], chest_contents[i] = chest_contents[i], chest_contents[j]
          break

        # make sure staff of rain guy doesn't have the stones (potentially unwinnable)
#      if (chest_contents[19] == 15):
#        j = self.non_charlock_chest()
#        #                  don't remove the key from the throne room
#        while (j == 19 or (j in (4, 5, 6) and chest_contents[j] == 3)):
#          j = self.non_charlock_chest()
#        chest_contents[19],chest_contents[j] = chest_contents[j],chest_contents[19]
    self.chests[3::4] = chest_contents

  def non_charlock_chest(self):
    """
    Gives a random index of a chest that is not in Charlock

    rtype: int
    return: A chest index that is not in Charlock.
    """
    chest = random.randint(0, 23)
    # avoid 11-16 and chest 24 (they are in charlock)
    chest = chest + 6 if (chest > 10) else chest
    chest = chest + 1 if (chest > 23) else chest
    return chest

  def randomize_attack_patterns(self, ultra=False):
    """
    Randomizes attack patterns of enemies (whether or not they use spells/fire 
    breath).
    """
    new_patterns = [] # attack patterns
    new_ss_resist = self.enemy_stats[4::16] 
    for i in range(38):
      new_ss_resist[i] |= 0xf
      if random.randint(0,1): # 50/50 chance
        resist = random.randint(0,round(i/5))
        new_ss_resist[i] &= (0xf0 | resist)
        if ultra:
            new_patterns.append((random.randint(0,255)))
        else:
          if i <= 20:
            # heal, sleep, stopspell, hurt
            new_patterns.append((random.randint(0,11) << 4) | random.randint(0,3))
          elif i < 30:
            # healmore, heal, sleep, stopspell, fire breath, hurtmore
            new_patterns.append((random.randint(0,15) << 4) | random.randint(4, 11))
          else:
            # healmore, sleep, stopspell, strong fire breath, fire breath, hurtmore
            #we'll be nice and not give Axe Knight Dragonlord's breath.
            slot2 = random.randint(4, 11) if i == 33 else random.randint(4, 15)
            new_patterns.append((random.choice((0, 1, 3)) << 6) | 
                (random.randint(0, 3) << 4) | slot2)
      else:
        new_patterns.append(0)
    new_patterns.append(87) #Dragonlord form 1
    new_patterns.append(14) #Dragonlord form 2
    self.enemy_stats[3::16] = bytearray(new_patterns)
    self.enemy_stats[4::16] = bytearray(new_ss_resist)

  def shuffle_towns(self):
    """
    Shuffles the locations of towns on the map.
    """
    self.owmap.shuffle_warps()

#    warp_data = self.rom_data[self.warps_slice]
#    towns = [warp_data[153:156], warp_data[159:162], warp_data[162:165],
#             warp_data[180:183], warp_data[183:186], warp_data[186:189]]
#    caves = [warp_data[156:159], warp_data[168:171], warp_data[177:180],
#             warp_data[189:192], warp_data[192:195], warp_data[204:207],
#             warp_data[210:213]]
#    random.shuffle(towns)
#    random.shuffle(caves)
#    # make sure the rimuldar cave isn't inaccessible
#    # this could happen if it ends up in southern shrine position or
#    # behind a locked door when rimuldar is in it's normal location.
#    while (caves[3][0] == 21 or
#          (towns[3][0] == 11 and 21 in (caves[5][0], caves[6][0])) or
#          (towns[3][0] ==  9 and caves[6][0] == 21)):
#      random.shuffle(caves)
#    warp_data[153:156] = towns[0]
#    warp_data[159:162] = towns[1]
#    warp_data[162:165] = towns[2]
#    warp_data[180:183] = towns[3]
#    warp_data[183:186] = towns[4]
#    warp_data[186:189] = towns[5]
#
#    warp_data[156:159] = caves[0]
#    warp_data[168:171] = caves[1]
#    warp_data[177:180] = caves[2]
#    warp_data[189:192] = caves[3]
#    warp_data[192:195] = caves[4]
#    warp_data[204:207] = caves[5]
#    warp_data[210:213] = caves[6]
#    # randomly swap swamp cave exit with southern shrine
#    if (random.randint(0,1)):
#      warp_data[174:177],warp_data[189:192] = warp_data[189:192],warp_data[174:177]
#    self.rom_data[self.warps_slice] = warp_data

  def randomize_zones(self, ultra=False):
    """
    Randomizes which enemies are present in each zone.
    """
    new_zones = list()
    if ultra:
      #zone 0-1
      for i in range(0,10):
        new_zones.append(random.randint(0, 6))
      for i in range(0,90):
        new_zones.append(random.randint(0, 37))
    else:
      #zones 2-19 
      for j in range(5): 
        new_zones.append(int(random.randint(0, 6)/2))

      # zones 1-13 (Overworld)
      for i in range(1, 14):
        for j in range(5):
          enemy = random.randint(i * 2 - 2, min(37,round(i*3)))
          while enemy == 24: # don't add golem
            enemy = random.randint(i * 2 - 2, min(37,round(i*3)))
          new_zones.append(enemy)

      #zone 14 - Garin's Grave?
      for j in range(5): 
        new_zones.append(random.randint(7, 17))

      #zone 15 - Lower Garin's Grave
      for j in range(5): 
        new_zones.append(random.randint(15, 23))

      # zone 16-18 - Charlock
      for i in range(16, 19):
        for j in range(5):
          new_zones.append(random.randint(13+i, 37))

      # zone 19 - Rimuldar Tunnel
      for j in range(5):
        new_zones.append(random.randint(3, 11))
    self.zones = new_zones

  def randomize_shops(self):
    """
    Randomizes the items available in each weapon shop
    """
    weapons = (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 14, 15, 16)
    new_shop_inv = []
    # add 5 items to each shop
    for i in range(7):
      this_shop = []
      while(len(this_shop) < 5):
        new_item = random.choice(weapons)
        if not new_item in this_shop:
          this_shop.append(new_item)
      new_shop_inv.append(this_shop)

    # add an extra item to one shop since we have 36 slots.
    six_item_shop = random.randint(0, 6)
    new_item = random.choice(weapons)
    while new_item in new_shop_inv[six_item_shop]:
      new_item = random.choice(weapons)
    new_shop_inv[six_item_shop].append(new_item)
    
    # create the bytearray to insert into the rom. Shops are separated by an 
    # 0xfd byte
    self.shop_inventory = []
    for shop in new_shop_inv:
      shop.sort()
      self.shop_inventory += shop + [0xfd]


  def shuffle_searchables(self):
    """
    Shuffles the 3 searchable items in the game. (E.Armor, F.Flute, E.Token)
    """
    searchables = [self.rom_data[self.token_slice],
                   self.rom_data[self.flute_slice],
                   self.rom_data[self.armor_slice]]
    random.shuffle(searchables)
    self.token_loc = searchables[0]
    self.flute_loc = searchables[1]
    self.armor_loc = searchables[2]

  def randomize_growth(self, ultra=False):
    
    player_str = list(self.player_stats[0:180:6])
    player_agi = list(self.player_stats[1:180:6])
    player_hp  = list(self.player_stats[2:180:6])
    player_mp  = list(self.player_stats[3:180:6])

    if ultra:
      for i in range(len(player_str)):
        player_str[i] = round(player_str[i] * random.uniform(0.8, 1.2))
      for i in range(len(player_agi)):
        player_agi[i] = round(player_agi[i] * random.uniform(0.8, 1.2))
      for i in range(len(player_hp)):
        player_hp[i] = round(player_hp[i] * random.uniform(0.8, 1.2))
      for i in range(len(player_mp)):
        player_mp[i] = round(player_mp[i] * random.uniform(0.8, 1.2))
    else:
      for i in range(len(player_str)):
        player_str[i] = random.randint(4,200)
      for i in range(len(player_agi)):
        player_agi[i] = random.randint(4,200)
      for i in range(len(player_hp)):
        player_hp[i] = random.randint(10,255)
      for i in range(len(player_mp)):
        player_mp[i] = random.randint(0,255)

    player_str.sort()
    player_agi.sort()
    player_hp.sort()
    player_mp.sort()

    self.player_stats[0:180:6] = player_str
    self.player_stats[1:180:6] = player_agi
    self.player_stats[2:180:6] = player_hp
    self.player_stats[3:180:6] = player_mp

  def randomize_spell_learning(self, ultra=False):
    self.move_repel() # in case this hasn't been called yet.
    player_mp = self.player_stats[3::6]
    new_masks = []
    # choose the levels for new spells
    if ultra:
      for i in range(len(self.new_spell_levels)):
        self.new_spell_levels[i] = random.randint(0, 20)
    else:
      for i in range(len(self.new_spell_levels)):
        self.new_spell_levels[i] += random.randint(-2, 2)
    #adjust the spell masks to fit the new levels
    for i in range(30):
      mask = 0
      for j in range(len(self.new_spell_levels)):
        if self.new_spell_levels[j] <= i+1:
          mask |= 1 << j
      new_masks.append(mask)
      if mask: # give the player at least 3 mp if they have a spell to use.
        player_mp[i] = max(3, player_mp[i])
    mask1 = []
    mask2 = []
    # split the masks for use in the rom
    for mask in new_masks:
      mask1.append(mask & 0xff)
      mask2.append(mask >> 8)

    self.player_stats[3::6] = player_mp
    self.player_stats[5::6] = mask1
    self.player_stats[4::6] = mask2

  def update_drops(self):
    """
    Raises enemy XP and gold drops to those of the remakes.
    """
    remake_xp = [  1,  2,  3,  4,  8, 12, 16, 14, 15, 18, 12, 25, 28, 
                  31, 40, 42,255, 47, 52, 58, 58, 64, 70, 72,255,  6, 
                  78, 83, 90,120,135,105,120,130,180,155,172,255,  0,  0]
    # These are +1 for proper values in the ROM
    remake_gold=[  3,  5,  7,  9, 17, 21, 26, 22, 20, 31, 21, 43, 51, 
                  49, 61, 63,  7, 76, 81, 96,111,106,111,121, 11,255,
                 151,136,149,186,161,170,186,166,151,149,153,144,  0,  0]
    self.enemy_stats[6::16] = bytearray(remake_xp)
    self.enemy_stats[7::16] = bytearray(remake_gold)

  def update_mp_reqs(self, ultra=False):
    """
    Lowers the MP requirements of spells to that of the remake
    """
    #magic required for each spell, in order
    self.mp_reqs = [3, 2, 2, 2, 2, 6, 8, 2, 8, 5]
#    if ultra:
#      for i in range(10):
#        self.mp_reqs[i] = random.randint(1, 8)

  def update_enemy_hp(self):
    """
    Updates HP of enemies to that of the remake, where possible.
    """
    #dragonlord hp should be 204 and 350, but we want him beatable at lv 18
    remake_hp = [  2,  3,  5,  7, 12, 13, 13, 22, 26, 43, 16, 24, 28, 
                  18, 33, 39,  3, 48, 37, 35, 44, 37, 40, 40,153,110, 
                  47, 48, 38, 70, 72, 74, 65, 67, 98,135, 99,106,100,165]
    # randomize Dragonlord's second form HP somewhat 
    remake_hp[-1] -= random.randint(0, 15) # 150 - 165
    self.enemy_stats[2::16] = bytearray(remake_hp)

  def fix_fighters_ring(self):
    """
    Adds functionality for the fighter's ring (+2 to attack)
    """
    ring_patch1 = (0x20, 0x54, 0xff, 0xea)
    ring_patch2 = (0x85, 0xcd, 0xa5, 0xcf, 0x29, 0x20, 0xf0, 0x07, 0xa5, 
                   0xcc, 0x18, 0x69, 0x02, 0x85, 0xcc, 0xa5, 0xcf, 0x60)
    self.rom_data[0xf10c:0xf110] = bytearray(ring_patch1)
    self.rom_data[0xff64:0xff76] = bytearray(ring_patch2)

  def move_repel(self):
    """
    Moves the repel spell to level 8
    """
    for i in range(47, 90, 6):
      self.player_stats[i] |= 0x80
    self.rom_data[0xeb15] = 8

  def buff_heal(self):
    self.rom_data[0xdbce] = 15

  def patch_northern_shrine(self):
    """
    Removes the 2 blocks from around the shrine guardian so you can walk around 
    him.
    """
    self.rom_data[0xd77] = self.rom_data[0xd81] = 0x66

  def commit(self):
    # commit map
    self.owmap.commit()
    self.rom_data[self.enemy_stats_slice] = self.enemy_stats 
    self.rom_data[self.mp_req_slice] = self.mp_reqs
    self.rom_data[self.zones_slice] = self.zones
    self.rom_data[self.weapon_shop_inv_slice] = self.shop_inventory
    self.rom_data[self.token_slice] = self.token_loc
    self.rom_data[self.flute_slice] = self.flute_loc
    self.rom_data[self.armor_slice] = self.armor_loc
    self.rom_data[self.player_stats_slice] = self.player_stats
    self.rom_data[self.new_spell_slice] = self.new_spell_levels
    self.rom_data[self.chests_slice] = self.chests

  def write(self, output_filename):
    outputfile = open(output_filename, 'wb')
    outputfile.write(self.rom_data)
    outputfile.close()

def main():
  
  parser = argparse.ArgumentParser(prog="DWRandomizer",
      description="A randomizer for Dragon Warrior for NES")
  parser.add_argument("-r","--remake", action="store_false",
      help="Do not set enemy HP, XP/Gold drops and MP use up to that of the "
           "remake. This will make grind times much longer.")
  parser.add_argument("-c","--chests", action="store_false",
      help="Do not randomize chest contents.")
  parser.add_argument("-f","--force", action="store_false", 
      help="Skip checksums and force randomization. This may produce an invalid"
           " ROM if the incorrect file is used.")
  parser.add_argument("-i","--searchitems", action="store_false", 
      help="Do not randomize the locations of searchable items (Fairy Flute, "
           "Erdrick's Armor, Erdrick's Token).")
  parser.add_argument("-g","--growth", action="store_false", 
      help="Do not randomize player stat growth.")
  parser.add_argument("-G","--ultra-growth", action="store_true", 
      help="Enable ultra randomization of player stat growth.")
  parser.add_argument("-l","--repel", action="store_false", 
      help="Do not move repel to level 8.")
  parser.add_argument("-m","--spells", action="store_false", 
      help="Do not randomize the level spells are learned.")
  parser.add_argument("-M","--ultra-spells", action="store_true", 
      help="Enable ultra randomization of the level spells are learned.")
  parser.add_argument("-a", "--map", action="store_true", 
      help=argparse.SUPPRESS) #"Generate a new world map. VERY EXPERIMENTAL!")
  parser.add_argument("-p","--patterns", action="store_false", 
      help="Do not randomize enemy attack patterns.")
  parser.add_argument("-P","--ultra-patterns", action="store_true", 
      help="Enable ultra randomization of enemy attack patterns.")
  parser.add_argument("-s","--seed", type=int, 
      help="Specify a seed to be used for randomization.")
  parser.add_argument("-t","--towns", action="store_false", 
      help="Do not randomize towns.")
  parser.add_argument("-w","--shops", action="store_false", 
      help="Do not randomize weapon shops.")
  parser.add_argument("-U","--ultra", action="store_true", 
      help="Enable all '--ultra' options.")
#  parser.add_argument('--version', action='version', version='%(prog) %s'%VERSION)
  parser.add_argument("-z","--zones", action="store_false", 
      help="Do not randomize enemy zones.")
  parser.add_argument("-Z","--ultra-zones", action="store_true", 
      help="Enable ultra randomization of enemy zones.")
  parser.add_argument("filename", help="The rom file to use for input")
  args = parser.parse_args()
  randomize(args)

def randomize(args):

  rom = Rom(args.filename)

  if not args.seed:
    args.seed = random.randint(0, sys.maxsize)
  print("Randomizing %s using random seed %d..." % (args.filename, args.seed))
  random.seed(args.seed)
  flags = ""
  prg = ""

  if args.force:
    print("Verifying checksum...")
    result = rom.verify_checksum()
    if result is False:
      print("Checksum does not match any known ROM, aborting.")
      print("Rerun with -f to force randomization.")
      sys.exit(-1)
    else:
      print("Processing Dragon Warrior PRG%d ROM..." % result)
      prg = "PRG%d." % result
      
  else:
    print("Skipping checksum...")

  print("Fixing functionality of the fighter's ring (+2 atk)...")
  rom.fix_fighters_ring()

  print("Buffing HEAL slightly...")
  rom.buff_heal()

  print("Fixing Northern Shrine...")
  rom.patch_northern_shrine()

  if args.searchitems:
    print("Shuffling searchable item locations...")
    flags += "i"
    rom.shuffle_searchables()

  if args.chests:
    print("Shuffling chest contents...")
    flags += "c"
    rom.shuffle_chests()

  if args.towns:
    print("Shuffling town locations...")
    flags += "t"
    rom.shuffle_towns()

  if args.zones:
    if args.ultra or args.ultra_zones:
      print("Ultra randomizing enemy zones...")
      flags += "Z"
      rom.randomize_zones(True)
    else:
      print("Randomizing enemy zones...")
      flags += "z"
      rom.randomize_zones()

  if args.patterns:
    if args.ultra or args.ultra_patterns:
      print("Ultra randomizing enemy attack patterns...")
      flags += "P"
      rom.randomize_attack_patterns(True)
    else:
      print("Randomizing enemy attack patterns...")
      flags += "p"
      rom.randomize_attack_patterns()

  if args.shops:
    print("Randomizing weapon shops...")
    flags += "w"
    rom.randomize_shops()

  if args.growth:
    if args.ultra or args.ultra_growth:
      print("Ultra randomizing player stat growth...")
      flags += "G"
      rom.randomize_growth(True)
    else:
      print("Randomizing player stat growth...")
      flags += "g"
      rom.randomize_growth()

  if args.remake:
    print("Increasing XP/Gold drops to remake levels...")
    flags += "r"
    rom.update_drops()
    print("Setting enemy HP to approximate remake levels...")
    rom.update_enemy_hp()
    print("Lowering MP requirements to remake levels...")
    rom.update_mp_reqs()

  if args.repel:
    print("Moving REPEL to level 8...")
    flags += "l"
    rom.move_repel()

  if args.spells:
    if args.ultra or args.ultra_spells:
      print("Ultra randomizing level spells are learned...")
      flags += "M"
      rom.randomize_spell_learning(True)
    else:
      print("Randomizing level spells are learned...")
      flags += "m"
      rom.randomize_spell_learning()

  if args.map:
    print("Generating new overworld map (experimental)...")
    flags += "a"
    rom.owmap.generate()
    while len(rom.owmap.encoded) > 2534:
      print(("Generated map is too large after encoding (%d/2534 bytes), "
             "regenerating... ") % len(rom.owmap.encoded))
      rom.owmap.generate()

  rom.commit()
  output_filename = "DWRando.%s.%d.%snes" % (flags, args.seed, prg)
  print("Writing output file %s..." % output_filename)
  rom.write(output_filename)
  print ("New ROM Checksum: %s" % rom.sha1())

if __name__ == "__main__":
  main()

