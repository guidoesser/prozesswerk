#!/usr/bin/env node
/**
 * ELK.js Layout Engine für BPMN-Diagramme.
 *
 * Liest einen flachen ELK-Graphen (JSON) von stdin, berechnet das Layout mit
 * ELK Layered (Sugiyama) + orthogonalen Kanten und gibt das komplette
 * Layout-JSON auf stdout aus.
 *
 * Der Eingabe-Graph hat diese Struktur:
 * {
 *   "id": "root",
 *   "layoutOptions": { ... },
 *   "children": [
 *     { "id": "NodeId", "width": 100, "height": 80 },
 *     ...
 *   ],
 *   "edges": [
 *     { "id": "Flow_X", "sources": ["NodeId"], "targets": ["NodeId"] },
 *     ...
 *   ]
 * }
 *
 * Usage:
 *   cat graph.json | node elk-layout.js > layout.json
 */

const ELK = require('elkjs/lib/elk.bundled.js');

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const input = Buffer.concat(chunks).toString('utf8');
  const graph = JSON.parse(input);

  const elk = new ELK();

  // Default-Layout-Optionen, die vom Aufrufer überschrieben werden können
  const defaults = {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.edgeRouting': 'ORTHOGONAL',
    'elk.layered.spacing.nodeNode': '60',
    'elk.layered.spacing.edgeNode': '30',
    'elk.layered.spacing.edgeEdge': '15',
    'elk.layered.spacing.nodeNodeBetweenLayers': '80',
    'elk.spacing.nodeNode': '40',
    'elk.spacing.edgeEdge': '10',
    'elk.padding': '[top=30,left=20,bottom=20,right=20]',
    'elk.layered.mergeEdges': 'false',
    'elk.layered.considerModelOrder.strategy': 'PREFER_EDGES',
    'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
    'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  };

  // Aufrufer-Optionen überschreiben Defaults
  const mergedOptions = { ...defaults, ...(graph.layoutOptions || {}) };
  graph.layoutOptions = mergedOptions;

  try {
    const layout = await elk.layout(graph);
    process.stdout.write(JSON.stringify(layout, null, 2));
  } catch (err) {
    console.error('ELK Layout Error:', err.message);
    process.exit(1);
  }
}

main();
