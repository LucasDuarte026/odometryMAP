import folium
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.signal import savgol_filter
import os
import json
import re
import sys
import numpy as np

def integrate_acceleration(csv_path):
    """
    Lê dados de um acelerômetro, aplica um filtro e realiza dupla integração
    para calcular os vetores de deslocamento em cada eixo.
    """
    # Lê o arquivo CSV
    df = pd.read_csv(csv_path, sep=",")
    
    # Extrai os valores para arrays numpy
    t = df["Time (s)"].values
    ax = df["Linear Acceleration x (m/s^2)"].values
    ay = df["Linear Acceleration y (m/s^2)"].values
    az = df["Linear Acceleration z (m/s^2)"].values

    # --- 1. Filtragem para reduzir ruído ---
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

    return dx, dy, dz, len(t)

def parse_device_info(device_csv_path):
    """Extrai informações do dispositivo do arquivo device.csv"""
    df = pd.read_csv(device_csv_path)
    device_info = {}
    
    for _, row in df.iterrows():
        device_info[row['property']] = row['value']
    
    return device_info

def parse_time_info(time_csv_path):
    """Extrai informações de tempo do arquivo time.csv"""
    df = pd.read_csv(time_csv_path)
    time_info = {}
    
    for _, row in df.iterrows():
        if row['event'] == 'START':
            time_info['start_time'] = row['system time text']
        elif row['event'] == 'PAUSE':
            time_info['end_time'] = row['system time text']
            time_info['duration'] = row['experiment time']
    
    return time_info

def calculate_acceleration_frequency(csv_path):
    """Calcula a frequência de captura dos dados de aceleração"""
    df = pd.read_csv(csv_path, sep=",")
    times = df["Time (s)"].values
    
    if len(times) > 1:
        avg_interval = (times[-1] - times[0]) / (len(times) - 1)
        frequency = 1.0 / avg_interval if avg_interval > 0 else 0
        return frequency, len(times)
    
    return 0, len(times)

def filter_diverging_gps_points(latitudes, longitudes, max_points_to_check=10):
    """
    Remove pontos GPS divergentes do início (normalmente o primeiro ponto)
    usando análise da diferença linear mediana
    """
    if len(latitudes) < max_points_to_check:
        return latitudes, longitudes, 0
    
    # Calcula distâncias consecutivas para os primeiros pontos
    distances = []
    for i in range(1, min(max_points_to_check + 1, len(latitudes))):
        lat_diff = latitudes[i] - latitudes[i-1]
        lon_diff = longitudes[i] - longitudes[i-1]
        distance = np.sqrt(lat_diff**2 + lon_diff**2)
        distances.append(distance)
    
    if len(distances) < 3:
        return latitudes, longitudes, 0
    
    # Calcula a mediana das distâncias
    median_distance = np.median(distances)
    
    # Encontra pontos que excedem 2x a mediana
    points_to_remove = 0
    threshold = 2 * median_distance
    
    for i, distance in enumerate(distances):
        if distance > threshold:
            points_to_remove = i + 1  # +1 porque distances[i] é a distância do ponto i+1
        else:
            break  # Para no primeiro ponto que não excede o threshold
    
    if points_to_remove > 0:
        print(f"🔧 Removendo {points_to_remove} pontos GPS divergentes do início")
        return latitudes[points_to_remove:], longitudes[points_to_remove:], points_to_remove
    
    return latitudes, longitudes, 0

def create_enhanced_map(file_name):
    """Cria um mapa aprimorado com interface GUI"""
    # Carrega dados GPS
    df_gps = pd.read_csv(f"./data/{file_name}/Location.csv")
    raw_latitudes = df_gps["Latitude (°)"].values
    raw_longitudes = df_gps["Longitude (°)"].values
    
    # Filtra pontos GPS divergentes
    latitudes, longitudes, removed_points = filter_diverging_gps_points(raw_latitudes, raw_longitudes)
    coords = list(zip(latitudes, longitudes))
    
    # Calcula centro do mapa
    center_lat = sum(latitudes) / len(latitudes)
    center_lon = sum(longitudes) / len(longitudes)
    
    # Processa dados de aceleração
    accel_path = f"./data/{file_name}/Linear Acceleration.csv"
    dx_vec, dy_vec, dz_vec, accel_points = integrate_acceleration(accel_path)
    accel_freq, _ = calculate_acceleration_frequency(accel_path)
    
    # Carrega informações do dispositivo e tempo
    device_info = parse_device_info(f"./data/{file_name}/meta/device.csv")
    time_info = parse_time_info(f"./data/{file_name}/meta/time.csv")
    
    # Parse da data do nome do arquivo
    date_parts = file_name.split('_')
    date_str = date_parts[0]
    time_str = date_parts[1].replace('-', ':')
    
    # Cria o mapa com zoom mais suave
    map_folium = folium.Map(
        location=[center_lat, center_lon], 
        zoom_start=17,
        tiles='OpenStreetMap',
        zoom_control=True,
        scrollWheelZoom=True,
        doubleClickZoom=True,
        boxZoom=True,
        keyboard=True,
        dragging=True,
        zoomSnap=0.5,  # Permite zoom em incrementos de 0.5
        zoomDelta=0.5  # Controla o incremento do zoom com botões
    )

    # Adiciona trajeto com cor moderna
    folium.PolyLine(
        locations=coords,
        color="#8B5CF6", 
        weight=4,
        opacity=0.9
    ).add_to(map_folium)
    
    # Adiciona marcadores nos pontos inicial e final
    folium.Marker(
        coords[0], 
        popup="Ponto Inicial",
        icon=folium.Icon(color='green', icon='play')
    ).add_to(map_folium)
    
    folium.Marker(
        coords[-1], 
        popup="Ponto Final",
        icon=folium.Icon(color='red', icon='stop')
    ).add_to(map_folium)
    
    # Calcula deslocamentos finais vetoriais
    delta_x = dx_vec[-1] if len(dx_vec) > 0 else 0
    delta_y = dy_vec[-1] if len(dy_vec) > 0 else 0
    delta_z = dz_vec[-1] if len(dz_vec) > 0 else 0
    
    # Salva o mapa temporariamente
    temp_path = f"tracks/temp_{file_name}.html"
    map_folium.save(temp_path)
    
    # Lê o HTML gerado pelo Folium
    with open(temp_path, 'r', encoding='utf-8') as f:
        original_html = f.read()
    
    # Extrai componentes necessários
    leaflet_css = re.findall(r'<link[^>]*leaflet[^>]*>', original_html)
    leaflet_js = re.findall(r'<script[^>]*leaflet[^>]*>.*?</script>', original_html, re.DOTALL)
    map_div = re.search(r'(<div[^>]*id="map_[^"]*"[^>]*>.*?</div>)', original_html, re.DOTALL)
    map_script = re.findall(r'<script[^>]*>.*?var map_[^;]*;.*?</script>', original_html, re.DOTALL)
    
    # Remove arquivo temporário
    os.remove(temp_path)
    
    # Cria HTML customizado completo
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Map Odometry Analysis - {file_name}</title>
    {''.join(leaflet_css)}
    <style>
        .main-title {{
            position: fixed; top: 15px; left: 60px; z-index: 1000;
            background: linear-gradient(135deg, #8B5CF6 0%, #A855F7 50%, #C084FC 100%);
            color: white; padding: 15px 25px; border-radius: 20px;
            box-shadow: 0 10px 40px rgba(139, 92, 246, 0.4);
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            font-size: 22px; font-weight: 700;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            letter-spacing: -0.025em;
        }}
        
        .data-panel {{
            position: fixed; bottom: 20px; left: 60px; z-index: 1000;
            background: rgba(255, 255, 255, 0.96); border-radius: 20px;
            box-shadow: 0 12px 48px rgba(139, 92, 246, 0.15);
            backdrop-filter: blur(16px); border: 1px solid rgba(139, 92, 246, 0.2);
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            min-width: 370px;
        }}
        
        .panel-tabs {{ display: flex; border-bottom: 1px solid rgba(139, 92, 246, 0.15); }}
        
        .tab-button {{
            flex: 1; padding: 14px 18px; background: none; border: none;
            cursor: pointer; font-weight: 600; color: #6B7280;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
            border-radius: 20px 20px 0 0; font-size: 14px;
        }}
        
        .tab-button.active {{ 
            background: linear-gradient(135deg, #8B5CF6, #A855F7); 
            color: white; transform: translateY(-1px);
        }}
        .tab-button:hover:not(.active) {{ 
            background: rgba(139, 92, 246, 0.08); color: #8B5CF6; 
        }}
        
        .tab-content {{ padding: 20px; display: none; }}
        .tab-content.active {{ display: block; }}
        
        .data-item {{
            margin-bottom: 12px; display: flex;
            justify-content: space-between; align-items: center;
        }}
        
        .data-label {{ font-weight: 600; color: #374151; }}
        .data-value {{ color: #8B5CF6; font-weight: 700; }}
        
        .home-button {{
            position: fixed; top: 100px; left: 60px; z-index: 1000;
            background: linear-gradient(135deg, #10B981, #059669); 
            color: white; border: none;
            padding: 14px 22px; border-radius: 30px; cursor: pointer;
            font-weight: 600; box-shadow: 0 6px 24px rgba(16, 185, 129, 0.3);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            font-size: 14px; letter-spacing: -0.025em;
        }}
        
        .home-button:hover {{
            background: linear-gradient(135deg, #059669, #047857); 
            transform: translateY(-3px);
            box-shadow: 0 8px 32px rgba(16, 185, 129, 0.4);
        }}
        
        .info-button {{
            position: fixed; top: 160px; left: 60px; z-index: 1000;
            background: linear-gradient(135deg, #3B82F6, #2563EB); 
            color: white; border: none;
            padding: 14px 22px; border-radius: 30px; cursor: pointer;
            font-weight: 600; box-shadow: 0 6px 24px rgba(59, 130, 246, 0.3);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            font-size: 14px; letter-spacing: -0.025em;
        }}
        
        .info-button:hover {{
            background: linear-gradient(135deg, #2563EB, #1D4ED8); 
            transform: translateY(-3px);
            box-shadow: 0 8px 32px rgba(59, 130, 246, 0.4);
        }}
        
        .modal {{
            display: none; position: fixed; z-index: 2000;
            left: 0; top: 0; width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.5); backdrop-filter: blur(5px);
        }}
        
        .modal-content {{
            background-color: #fefefe; margin: 5% auto; padding: 30px;
            border-radius: 15px; width: 80%; max-width: 600px;
            max-height: 80vh; overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        
        .close {{
            color: #aaa; float: right; font-size: 28px;
            font-weight: bold; cursor: pointer; margin-top: -10px;
        }}
        .close:hover {{ color: #000; }}
        
        .device-info {{
            display: grid; grid-template-columns: 1fr 2fr;
            gap: 10px; margin-bottom: 10px;
        }}
        .device-info strong {{ color: #333; }}
        
        .datetime-info {{
            background: linear-gradient(135deg, #EC4899, #BE185D);
            color: white; padding: 12px 18px; border-radius: 16px;
            margin-bottom: 12px; text-align: center; font-weight: 600;
            font-size: 15px; letter-spacing: -0.025em;
            box-shadow: 0 4px 20px rgba(236, 72, 153, 0.3);
        }}
    </style>
    {''.join(leaflet_js)}
</head>
<body>
    <div class="main-title">📍 Map Odometry Analysis</div>
    
    <button class="home-button" onclick="centerMap()">🎯 Home</button>
    <button class="info-button" onclick="openModal()">📱 Device Info</button>
    
    <div class="data-panel">
        <div class="datetime-info">📅 {date_str} ⏰ {time_str}</div>
        
        <div class="panel-tabs">
            <button class="tab-button active" onclick="switchTab('data')">📈 Analytics</button>
            <button class="tab-button" onclick="switchTab('displacement')">🧭 Displacement</button>
        </div>
        
        <div id="data-tab" class="tab-content active">
            <div class="data-item">
                <span class="data-label">GPS Points:</span>
                <span class="data-value">{len(coords)}</span>
            </div>
            <div class="data-item">
                <span class="data-label">Accel. Points:</span>
                <span class="data-value">{accel_points:,}</span>
            </div>
            <div class="data-item">
                <span class="data-label">Accel. Frequency:</span>
                <span class="data-value">{accel_freq:.1f} Hz</span>
            </div>
            <div class="data-item">
                <span class="data-label">Duration:</span>
                <span class="data-value">{time_info.get('duration', 0):.1f}s</span>
            </div>
        </div>
        
        <div id="displacement-tab" class="tab-content">
            <div class="data-item">
                <span class="data-label">Δx:</span>
                <span class="data-value">{delta_x:.3f} m</span>
            </div>
            <div class="data-item">
                <span class="data-label">Δy:</span>
                <span class="data-value">{delta_y:.3f} m</span>
            </div>
            <div class="data-item">
                <span class="data-label">Δz:</span>
                <span class="data-value">{delta_z:.3f} m</span>
            </div>
            <div class="data-item">
                <span class="data-label">Total:</span>
                <span class="data-value">{(delta_x**2 + delta_y**2 + delta_z**2)**0.5:.3f} m</span>
            </div>
        </div>
    </div>
    
    <div id="deviceModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2>🔧 Device Information</h2>
            
            <h3>📱 Device Details</h3>
            <div class="device-info">
                <strong>Model:</strong> <span>{device_info.get('deviceModel', 'N/A')}</span>
                <strong>Brand:</strong> <span>{device_info.get('deviceBrand', 'N/A')}</span>
                <strong>Manufacturer:</strong> <span>{device_info.get('deviceManufacturer', 'N/A')}</span>
                <strong>Android Version:</strong> <span>{device_info.get('deviceRelease', 'N/A')}</span>
            </div>
            
            <h3>🛰️ GPS Sensor</h3>
            <div class="device-info">
                <strong>Provider:</strong> <span>Android Location Services</span>
                <strong>Accuracy:</strong> <span>Variable (see map data)</span>
            </div>
            
            <h3>⚡ Linear Acceleration Sensor</h3>
            <div class="device-info">
                <strong>Name:</strong> <span>{device_info.get('linear_acceleration Name', 'N/A')}</span>
                <strong>Vendor:</strong> <span>{device_info.get('linear_acceleration Vendor', 'N/A')}</span>
                <strong>Range:</strong> <span>{device_info.get('linear_acceleration Range', 'N/A')} m/s²</span>
                <strong>Resolution:</strong> <span>{device_info.get('linear_acceleration Resolution', 'N/A')} m/s²</span>
                <strong>Min Delay:</strong> <span>{device_info.get('linear_acceleration MinDelay', 'N/A')} μs</span>
                <strong>Power:</strong> <span>{device_info.get('linear_acceleration Power', 'N/A')} mA</span>
            </div>
            
            <h3>🔬 Other Sensors Available</h3>
            <div class="device-info">
                <strong>Accelerometer:</strong> <span>{device_info.get('accelerometer Name', 'N/A')}</span>
                <strong>Gyroscope:</strong> <span>{device_info.get('gyroscope Name', 'N/A')}</span>
                <strong>Magnetometer:</strong> <span>{device_info.get('magnetic_field Name', 'N/A')}</span>
                <strong>Pressure:</strong> <span>{device_info.get('pressure Name', 'N/A')}</span>
            </div>
        </div>
    </div>
    
    {map_div.group(1) if map_div else '<div id="map" style="width: 100%; height: 100vh;"></div>'}
    
    {''.join(map_script)}
    
    <script>
        const centerCoords = [{center_lat}, {center_lon}];
        const allCoords = {json.dumps(coords)};
        
        function switchTab(tabName) {{
            document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');
        }}
        
        function centerMap() {{
            const mapElements = document.querySelectorAll('[id^="map_"]');
            if (mapElements.length > 0 && window[mapElements[0].id]) {{
                const mapObj = window[mapElements[0].id];
                
                const lats = allCoords.map(coord => coord[0]);
                const lngs = allCoords.map(coord => coord[1]);
                
                const bounds = [
                    [Math.min(...lats), Math.min(...lngs)],
                    [Math.max(...lats), Math.max(...lngs)]
                ];
                
                mapObj.fitBounds(bounds, {{padding: [50, 50]}});
            }}
        }}
        
        function openModal() {{
            document.getElementById('deviceModal').style.display = 'block';
        }}
        
        function closeModal() {{
            document.getElementById('deviceModal').style.display = 'none';
        }}
        
        window.onclick = function(event) {{
            const modal = document.getElementById('deviceModal');
            if (event.target == modal) {{
                modal.style.display = 'none';
            }}
        }}
    </script>
</body>
</html>"""
    
    # Salva o HTML final
    output_path = f"tracks/track_{file_name}.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return {
        'gps_points': len(coords),
        'accel_points': accel_points,
        'accel_frequency': accel_freq,
        'displacement': {'x': delta_x, 'y': delta_y, 'z': delta_z},
        'device_info': device_info,
        'time_info': time_info,
        'removed_points': removed_points
    }

# Configuração do arquivo a ser processado
file_name = sys.argv[1]

if __name__ == "__main__":
    print(f"\n🗺️ Processando dados de: {file_name}")
    print("=" * 50)
    
    results = create_enhanced_map(file_name)
    
    print(f"\n📊 Resultados da Análise:")
    print(f"  📍 Pontos GPS analisados: {results['gps_points']}")
    print(f"  📈 Pontos de aceleração: {results['accel_points']:,}")
    print(f"  ⚡ Frequência de captura: {results['accel_frequency']:.1f} Hz")
    if 'removed_points' in results and results['removed_points'] > 0:
        print(f"  🔧 Pontos GPS divergentes removidos: {results['removed_points']}")
    
    print(f"\n📐 Deslocamentos Vetoriais:")
    displacement = results['displacement']
    print(f"  Δx Final: {displacement['x']:.4f} metros")
    print(f"  Δy Final: {displacement['y']:.4f} metros")
    print(f"  Δz Final: {displacement['z']:.4f} metros")
    
    total_displacement = (displacement['x']**2 + displacement['y']**2 + displacement['z']**2)**0.5
    print(f"  📏 Deslocamento Total: {total_displacement:.4f} metros")
    
    print(f"\n📱 Dispositivo: {results['device_info'].get('deviceBrand', 'N/A')} {results['device_info'].get('deviceModel', 'N/A')}")
    
    print(f"\n✅ Mapa salvo em: tracks/track_{file_name}.html")
    print(f"🚀 Abra o arquivo no navegador para ver a interface interativa!")
