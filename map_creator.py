import folium
import pandas as pd

df = pd.read_csv("./data/2025-09-21--22-41-13/Location.csv")
# Extrai latitude e longitude
latitudes = df["Latitude (°)"].values
longitudes = df["Longitude (°)"].values
coords = list(zip(latitudes, longitudes))


# Centraliza no primeiro ponto
map = folium.Map(location=coords[0], zoom_start=20)

# Adiciona trajeto
folium.PolyLine(
    locations=coords,
    color="blue", weight=3
).add_to(map)

# Adiciona marcadores nos pontos
for i, (lat, lon) in enumerate(coords, start=1):
    folium.Marker([lat, lon], popup=f"Ponto {i}").add_to(map)

map.save("trajeto.html")
