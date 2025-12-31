/**
 * NYC Childhood Asthma Prevention Failure Map
 * Interactive bivariate choropleth visualization
 */

// Global state
let map;
let neighborhoodsData;
let providersData;
let statsData;
let selectedNeighborhood = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Load data
        await loadData();
        
        // Initialize map
        initMap();
        
        // Update header stats
        updateHeaderStats();
        
        // Setup event listeners
        setupEventListeners();
        
    } catch (error) {
        console.error('Failed to initialize application:', error);
    }
});

/**
 * Load all required data files
 */
async function loadData() {
    const cacheBuster = Date.now();

    const fetchJson = async (url) => {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to load ${url}: ${response.status} ${response.statusText}`);
        }
        return response.json();
    };

    try {
        const [neighborhoods, providers, stats] = await Promise.all([
            fetchJson(`data/neighborhoods.geojson?v=${cacheBuster}`),
            fetchJson(`data/providers.geojson?v=${cacheBuster}`),
            fetchJson(`data/stats.json?v=${cacheBuster}`)
        ]);

        neighborhoodsData = neighborhoods;
        providersData = providers;
        statsData = stats;

        console.log('Data loaded:', {
            neighborhoods: neighborhoods.features.length,
            providers: providers.features.length,
            stats: stats
        });
    } catch (error) {
        console.error('Failed to load data:', error);
        // Show user-friendly error message
        const mapContainer = document.getElementById('map');
        if (mapContainer) {
            mapContainer.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #e74c3c; text-align: center; padding: 2rem;">
                    <div>
                        <h2>Error Loading Data</h2>
                        <p>Unable to load map data. Please refresh the page or try again later.</p>
                        <p style="font-size: 0.8rem; color: #888;">${error.message}</p>
                    </div>
                </div>
            `;
        }
        throw error;
    }
}

/**
 * Initialize the MapLibre GL map
 */
function initMap() {
    map = new maplibregl.Map({
        container: 'map',
        style: {
            version: 8,
            sources: {
                'carto-dark': {
                    type: 'raster',
                    tiles: [
                        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
                        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
                        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png'
                    ],
                    tileSize: 256,
                    attribution: '&copy; <a href="https://carto.com/">CARTO</a>'
                }
            },
            layers: [{
                id: 'carto-dark-layer',
                type: 'raster',
                source: 'carto-dark',
                minzoom: 0,
                maxzoom: 20
            }]
        },
        center: [-73.95, 40.70],
        zoom: 10,
        minZoom: 9,
        maxZoom: 14
    });
    
    map.on('load', () => {
        addNeighborhoodLayers();
        addProviderLayer();
    });
    
    // Add navigation controls
    map.addControl(new maplibregl.NavigationControl(), 'top-left');
}

/**
 * Add neighborhood polygon layers
 */
function addNeighborhoodLayers() {
    // Add source
    map.addSource('neighborhoods', {
        type: 'geojson',
        data: neighborhoodsData
    });
    
    // Add fill layer
    map.addLayer({
        id: 'neighborhoods-fill',
        type: 'fill',
        source: 'neighborhoods',
        paint: {
            'fill-color': ['get', 'fill_color'],
            'fill-opacity': [
                'case',
                ['boolean', ['feature-state', 'hover'], false],
                0.9,
                0.75
            ]
        }
    });
    
    // Add outline layer
    map.addLayer({
        id: 'neighborhoods-outline',
        type: 'line',
        source: 'neighborhoods',
        paint: {
            'line-color': [
                'case',
                ['boolean', ['feature-state', 'selected'], false],
                '#ffffff',
                ['boolean', ['feature-state', 'hover'], false],
                '#ffffff',
                'rgba(255, 255, 255, 0.3)'
            ],
            'line-width': [
                'case',
                ['boolean', ['feature-state', 'selected'], false],
                3,
                ['boolean', ['feature-state', 'hover'], false],
                2,
                1
            ]
        }
    });
    
    // Add failure zone highlight
    map.addLayer({
        id: 'neighborhoods-failure-highlight',
        type: 'line',
        source: 'neighborhoods',
        filter: ['==', ['get', 'is_failure_zone'], true],
        paint: {
            'line-color': '#e74c3c',
            'line-width': 3,
            'line-dasharray': [2, 2]
        }
    });
    
    // Track hovered feature
    let hoveredId = null;
    
    // Hover effects
    map.on('mousemove', 'neighborhoods-fill', (e) => {
        if (e.features.length > 0) {
            if (hoveredId !== null) {
                map.setFeatureState(
                    { source: 'neighborhoods', id: hoveredId },
                    { hover: false }
                );
            }
            hoveredId = e.features[0].id;
            map.setFeatureState(
                { source: 'neighborhoods', id: hoveredId },
                { hover: true }
            );
            map.getCanvas().style.cursor = 'pointer';
        }
    });
    
    map.on('mouseleave', 'neighborhoods-fill', () => {
        if (hoveredId !== null) {
            map.setFeatureState(
                { source: 'neighborhoods', id: hoveredId },
                { hover: false }
            );
        }
        hoveredId = null;
        map.getCanvas().style.cursor = '';
    });
    
    // Click handler
    map.on('click', 'neighborhoods-fill', (e) => {
        if (e.features.length > 0) {
            selectNeighborhood(e.features[0]);
        }
    });
}

/**
 * Add provider point layer
 */
function addProviderLayer() {
    // Add source
    map.addSource('providers', {
        type: 'geojson',
        data: providersData
    });
    
    // Add circle layer (initially hidden)
    map.addLayer({
        id: 'providers-circle',
        type: 'circle',
        source: 'providers',
        layout: {
            'visibility': 'none'
        },
        paint: {
            'circle-radius': [
                'interpolate',
                ['linear'],
                ['zoom'],
                9, 2,
                14, 6
            ],
            'circle-color': '#ffffff',
            'circle-stroke-color': '#0a0e17',
            'circle-stroke-width': 1,
            'circle-opacity': 0.8
        }
    });
    
    // Hover popup for providers
    const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        className: 'provider-popup'
    });
    
    map.on('mouseenter', 'providers-circle', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        
        const props = e.features[0].properties;
        const html = `
            <strong>${props.name}</strong>
            ${props.credential ? `<span>, ${props.credential}</span>` : ''}
            <br>
            <small>${props.specialty}</small>
        `;
        
        popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
    });
    
    map.on('mouseleave', 'providers-circle', () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
    });
}

/**
 * Select a neighborhood and update info panel
 */
function selectNeighborhood(feature) {
    // Clear previous selection
    if (selectedNeighborhood !== null) {
        map.setFeatureState(
            { source: 'neighborhoods', id: selectedNeighborhood },
            { selected: false }
        );
    }
    
    // Set new selection
    selectedNeighborhood = feature.id;
    map.setFeatureState(
        { source: 'neighborhoods', id: selectedNeighborhood },
        { selected: true }
    );
    
    // Update info panel
    updateInfoPanel(feature.properties);
    
    // On mobile, expand the info panel
    document.getElementById('info-panel').classList.add('expanded');
}

/**
 * Update the info panel with neighborhood data
 */
function updateInfoPanel(props) {
    document.getElementById('info-neighborhood').textContent = props.uhf_name;
    document.getElementById('info-borough').textContent = props.borough;
    
    // Determine status badge
    let badge = '';
    if (props.is_failure_zone) {
        badge = '<span class="info-badge failure">Failure Zone</span>';
    } else if (props.is_at_risk) {
        badge = '<span class="info-badge at-risk">At Risk</span>';
    } else if (props.bivariate_class === '1-1') {
        badge = '<span class="info-badge good">Best Access</span>';
    }
    
    // Calculate comparison text
    const erComparison = props.er_pct_of_avg > 100 
        ? `${Math.round(props.er_pct_of_avg - 100)}% above average`
        : `${Math.round(100 - props.er_pct_of_avg)}% below average`;
    
    const providerComparison = props.provider_pct_of_avg > 100
        ? `${Math.round(props.provider_pct_of_avg - 100)}% above average`
        : `${Math.round(100 - props.provider_pct_of_avg)}% below average`;
    
    // Determine value classes
    const erClass = props.er_tercile === 3 ? 'danger' : (props.er_tercile === 1 ? 'success' : '');
    const providerClass = props.access_tercile === 3 ? 'danger' : (props.access_tercile === 1 ? 'success' : '');
    
    const html = `
        ${badge ? `<div style="margin-bottom: 1rem;">${badge}</div>` : ''}
        <div class="info-stats">
            <div class="info-stat-row">
                <span class="info-stat-label">Child Population</span>
                <span class="info-stat-value">${formatNumber(props.child_population)}</span>
            </div>
            <div class="info-stat-row">
                <span class="info-stat-label">ER Visits (per 10k)</span>
                <span class="info-stat-value ${erClass}">${props.er_rate_5to17}</span>
            </div>
            <div class="info-stat-row">
                <span class="info-stat-label">Total Providers</span>
                <span class="info-stat-value ${providerClass}">${props.total_providers}</span>
            </div>
            <div class="info-stat-row">
                <span class="info-stat-label">Providers (per 10k)</span>
                <span class="info-stat-value ${providerClass}">${props.providers_per_10k}</span>
            </div>
        </div>
        <div class="info-comparison">
            <strong>Compared to NYC average:</strong><br>
            ER visits: ${erComparison}<br>
            Provider access: ${providerComparison}
        </div>
    `;
    
    document.getElementById('info-body').innerHTML = html;
}

/**
 * Update header statistics
 */
function updateHeaderStats() {
    if (!statsData) return;
    
    document.getElementById('stat-children').textContent = 
        formatNumber(statsData.total_children);
    
    document.getElementById('stat-failure-zones').textContent = 
        statsData.failure_zones.count;
    
    document.getElementById('stat-affected').textContent = 
        formatNumber(statsData.failure_zones.children);
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Provider toggle
    const providerToggle = document.getElementById('toggle-providers');
    providerToggle.addEventListener('change', (e) => {
        const visibility = e.target.checked ? 'visible' : 'none';
        map.setLayoutProperty('providers-circle', 'visibility', visibility);
    });
    
    // Mobile info panel toggle
    const infoPanel = document.getElementById('info-panel');
    const infoPanelHeader = document.querySelector('.info-panel-header');
    
    infoPanelHeader.addEventListener('click', () => {
        if (window.innerWidth <= 768) {
            infoPanel.classList.toggle('expanded');
        }
    });
    
    // Legend cell hover and keyboard support
    const legendCells = document.querySelectorAll('.legend-cell');
    legendCells.forEach(cell => {
        cell.addEventListener('mouseenter', () => {
            const cls = cell.dataset.class;
            highlightClass(cls);
        });

        cell.addEventListener('mouseleave', () => {
            clearHighlight();
        });

        // Keyboard support for accessibility
        cell.addEventListener('focus', () => {
            const cls = cell.dataset.class;
            highlightClass(cls);
        });

        cell.addEventListener('blur', () => {
            clearHighlight();
        });

        cell.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const cls = cell.dataset.class;
                highlightClass(cls);
            }
        });
    });
}

/**
 * Highlight neighborhoods of a specific bivariate class
 */
function highlightClass(bivarClass) {
    map.setPaintProperty('neighborhoods-fill', 'fill-opacity', [
        'case',
        ['==', ['get', 'bivariate_class'], bivarClass],
        0.95,
        0.3
    ]);
}

/**
 * Clear class highlight
 */
function clearHighlight() {
    map.setPaintProperty('neighborhoods-fill', 'fill-opacity', [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        0.9,
        0.75
    ]);
}

/**
 * Format large numbers with commas
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '—';
    return num.toLocaleString();
}

