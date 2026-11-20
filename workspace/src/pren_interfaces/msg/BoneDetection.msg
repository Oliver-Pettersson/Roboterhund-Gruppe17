# Ergebnis der Knochenerkennung relativ zum Roboter (frame_id = base_link).

std_msgs/Header header
bool detected          # true, wenn ein Knochen im Bild bzw. Sichtkegel ist
float32 distance_m     # Distanz zum Knochen in Metern (nur gueltig, wenn detected)
float32 bearing_rad    # Winkel zum Knochen, positiv = links (nur gueltig, wenn detected)
float32 confidence     # 0.0 bis 1.0
