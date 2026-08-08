from fieldops.state import Tile
t = Tile("PLANT", crop="MELON")
print(t.is_plant())
print(getattr(t, 'is_plant', lambda: False)())
