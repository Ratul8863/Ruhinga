"""
Targeted PyQGIS ring-level duplicate-node cleaning for the 2018 dissolved
IOM NPM camp/site extent.

Run in the QGIS Python Console only on the already dissolved 38-site layer.
The input raw Majhee Blocks archive is never edited. Write output to a new
GeoPackage and validate it with QGIS Check Validity (strict method) afterward.
"""

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorFileWriter


INPUT_LAYER_NAME = "camp_admin_extent_2018_ringclean"
OUTPUT_GPKG = r"F:\Ratul\Ruhinga\Rohingya_Forest_Impact_Research\04_Data\02_Camp_Exposure\Processed\camp_admin_extent_2018_ringclean_v2.gpkg"
OUTPUT_LAYER_NAME = "camp_admin_extent_2018_ringclean_v2"


def remove_consecutive_duplicate_nodes(ring):
    """Return a closed QgsPointXY ring, removing consecutive equal vertices."""
    if not ring:
        return ring, 0
    cleaned = [QgsPointXY(ring[0])]
    removed = 0
    for point in ring[1:]:
        candidate = QgsPointXY(point)
        if candidate == cleaned[-1]:
            removed += 1
        else:
            cleaned.append(candidate)
    if len(cleaned) > 1 and cleaned[0] != cleaned[-1]:
        cleaned.append(QgsPointXY(cleaned[0]))
    return cleaned, removed


def clean_polygon_geometry(geometry):
    """Clean consecutive duplicates in polygon or multipolygon rings."""
    if geometry.isMultipart():
        parts = geometry.asMultiPolygon()
        cleaned_parts, removed_total = [], 0
        for polygon in parts:
            cleaned_polygon = []
            for ring in polygon:
                clean_ring, removed = remove_consecutive_duplicate_nodes(ring)
                cleaned_polygon.append(clean_ring)
                removed_total += removed
            cleaned_parts.append(cleaned_polygon)
        return QgsGeometry.fromMultiPolygonXY(cleaned_parts), removed_total

    polygon = geometry.asPolygon()
    cleaned_polygon, removed_total = [], 0
    for ring in polygon:
        clean_ring, removed = remove_consecutive_duplicate_nodes(ring)
        cleaned_polygon.append(clean_ring)
        removed_total += removed
    return QgsGeometry.fromPolygonXY(cleaned_polygon), removed_total


layer = next((item for item in QgsProject.instance().mapLayers().values()
              if item.name() == INPUT_LAYER_NAME), None)
if layer is None:
    raise RuntimeError(f"Layer not found: {INPUT_LAYER_NAME}")

options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "GPKG"
options.layerName = OUTPUT_LAYER_NAME
options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

writer = QgsVectorFileWriter.create(
    OUTPUT_GPKG,
    layer.fields(),
    layer.wkbType(),
    layer.crs(),
    QgsProject.instance().transformContext(),
    options,
)
if writer.hasError() != QgsVectorFileWriter.NoError:
    raise RuntimeError(writer.errorMessage())

removed_total = 0
for feature in layer.getFeatures():
    output = QgsFeature(layer.fields())
    output.setAttributes(feature.attributes())
    cleaned_geometry, removed = clean_polygon_geometry(feature.geometry())
    output.setGeometry(cleaned_geometry)
    writer.addFeature(output)
    removed_total += removed

del writer
print(f"Wrote {OUTPUT_GPKG}; removed {removed_total} consecutive duplicate node(s).")
print("Next: run strict Check Validity and record valid/invalid/error counts.")
