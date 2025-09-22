import folium
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.signal import savgol_filter

def integrate_accelatation(csv_path):
    """
    Lê dados de um acelerômetro, aplica um filtro e realiza dupla integração
    para calcular os vetores de deslocamento em cada eixo.
    """
    # Lê o arquivo CSV
    df = pd.read_csv(csv_path, sep=",")
    
    # Extrai os valores para arrays numpy
    t = df["Time (s)"].values
    ax = df["Acceleration x (m/s^2)"].values
    ay = df["Acceleration y (m/s^2)"].values
    az = df["Acceleration z (m/s^2)"].values

    # --- 1. Filtragem para reduzir ruído ---
    # Janela de 7 pontos e polinômio de grau 3 é um bom ponto de partida
    ax = savgol_filter(ax, 7, 3)
    ay = savgol_filter(ay, 7, 3)
    az = savgol_filter(az, 7, 3)

    # --- 2. Primeira Integração (Aceleração -> Velocidade) ---
    vx = cumulative_trapezoid(ax, t, initial=0)
    vy = cumulative_trapezoid(ay, t, initial=0)
    vz = cumulative_trapezoid(az, t, initial=0)

    # --- 3. Segunda Integração (Velocidade -> Deslocamento) ---
    dx = cumulative_trapezoid(vx, t, initial=0)
    dy = cumulative_trapezoid(vy, t, initial=0)
    dz = cumulative_trapezoid(vz, t, initial=0)

    # MUDANÇA 1: Retornar os três vetores (arrays) de deslocamento diretamente
    return dx, dy, dz


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


# MUDANÇA 2: Chamar a função e receber os três vetores em variáveis separadas
dx_vec, dy_vec, dz_vec = integrate_accelatation("./data/2025-09-21--22-41-13/Accelerometer.csv")

# MUDANÇA 3: Exibir os resultados de forma vetorial
print("\n--- Análise Vetorial do Acelerômetro ---")
print(f"Vetor de deslocamento em X ({len(dx_vec)} pontos):")
print(dx_vec)
print("-" * 30)
print(f"Vetor de deslocamento em Y ({len(dy_vec)} pontos):")
print(dy_vec)
print("-" * 30)
print(f"Vetor de deslocamento em Z ({len(dz_vec)} pontos):")
print(dz_vec)
print("-" * 30)

# Exibe o deslocamento final em cada eixo como um resumo
print("\nResumo do Deslocamento Final Calculado:")
print(f"  Δx Final: {dx_vec[-1]:.4f} metros")
print(f"  Δy Final: {dy_vec[-1]:.4f} metros")
print(f"  Δz Final: {dz_vec[-1]:.4f} metros")