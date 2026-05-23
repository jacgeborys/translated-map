<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.3-Firenze" styleCategories="Labeling" labelsEnabled="1">
  <!--
    places_translated — rule-based density labeling
    Load via: Layer Properties → Style → Load Style → select "Labeling" category

    Three tiers based on neighbour count within 0.2 °:
      isolated      (0 neighbours)  → 2 mm offset,  no callout
      few neighbors (1–2 neighbours) → 6 mm offset,  callout
      crowded       (>2 neighbours)  → 16 mm offset, callout

    Callout: simple dark line (#2a2a2a, 0.2 mm)
    Label field: name_eng waterfall → name:en → name:pinyin → name
    HTML rendering: Chinese name above (grey, smaller) / English below
  -->
  <labeling type="rule-based">
    <rules key="{5e57a92c-57a1-4d5e-8a2b-1c2d3e4f5a6b}">

      <!-- ================================================================
           Rule 1: ISOLATED — 0 neighbours within 0.2°
           dist = 2 mm, no callout
           ================================================================ -->
      <rule description="isolated"
            filter="aggregate('places_translated','count',$id,distance($geometry,geometry(@parent))&lt;0.2 AND $id!=attribute(@parent,'fid')) = 0"
            key="{5e57a92c-57a1-4d5e-8a2b-1c2d3e4f5a6c}">
        <settings calloutType="simple">
          <text-style textColor="42,42,42,255" textOrientation="horizontal"
              fontSizeMapUnitScale="3x:0,0,0,0,0,0" forcedBold="0" fontWeight="50"
              fontSize="8" blendMode="0" textOpacity="1" fontStrikeout="0"
              multilineHeight="1" fontUnderline="0" fontLetterSpacing="0"
              namedStyle="" fontFamily="Trebuchet MS" multilineHeightUnit="Percentage"
              legendString="Aa" capitalization="0" fontWordSpacing="0"
              previewBkgrdColor="255,255,255,255" useSubstitutions="0"
              fontSizeUnit="Point" isExpression="1" fontKerning="1"
              fieldName="concat(if(&quot;name&quot; IS NOT NULL AND &quot;name&quot; != coalesce(&quot;name_eng&quot;, &quot;name:en&quot;, &quot;name:pinyin&quot;, &quot;name&quot;), concat('&lt;span style=&quot;font-size:', to_string(CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 8 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 6 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 5 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 4 ELSE 4 END), 'pt; color:#888888&quot;>', &quot;name&quot;, '&lt;/span>&lt;br>'), ''), coalesce(&quot;name_eng&quot;, &quot;name:en&quot;, &quot;name:pinyin&quot;, &quot;name&quot;))"
              fontItalic="0" allowHtml="1" forcedItalic="0">
            <families/>
            <text-buffer bufferNoFill="1" bufferSizeUnits="MM"
                bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferOpacity="1"
                bufferSize="0.8" bufferColor="255,255,255,255"
                bufferBlendMode="0" bufferDraw="1" bufferJoinStyle="128"/>
            <text-mask maskEnabled="0" maskOpacity="1" maskSizeUnits="MM"
                maskSize="1.5" maskedSymbolLayers="" maskType="0"
                maskJoinStyle="128" maskSizeMapUnitScale="3x:0,0,0,0,0,0"/>
            <background shapeSizeX="0" shapeFillColor="255,255,255,255"
                shapeRadiiY="0" shapeBorderWidthUnit="MM" shapeOffsetX="0"
                shapeSVGFile="" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0"
                shapeBorderColor="128,128,128,255" shapeBorderWidth="0"
                shapeOffsetY="0" shapeJoinStyle="64" shapeRadiiX="0"
                shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeOpacity="1"
                shapeRotationType="0" shapeSizeY="0" shapeDraw="0"
                shapeRotation="0" shapeOffsetUnit="MM" shapeBlendMode="0"
                shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeSizeUnit="MM"
                shapeType="0" shapeSizeType="0"
                shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeRadiiUnit="MM">
              <symbol type="fill" clip_to_extent="1" is_animated="0" frame_rate="10" alpha="1" force_rhr="0" name="fillSymbol">
                <data_defined_properties>
                  <Option type="Map">
                    <Option type="QString" value="" name="name"/>
                    <Option name="properties"/>
                    <Option type="QString" value="collection" name="type"/>
                  </Option>
                </data_defined_properties>
                <layer class="SimpleFill" locked="0" pass="0" enabled="1">
                  <Option type="Map">
                    <Option type="QString" value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale"/>
                    <Option type="QString" value="255,255,255,255" name="color"/>
                    <Option type="QString" value="bevel" name="joinstyle"/>
                    <Option type="QString" value="0,0" name="offset"/>
                    <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
                    <Option type="QString" value="MM" name="offset_unit"/>
                    <Option type="QString" value="128,128,128,255" name="outline_color"/>
                    <Option type="QString" value="no" name="outline_style"/>
                    <Option type="QString" value="0" name="outline_width"/>
                    <Option type="QString" value="MM" name="outline_width_unit"/>
                    <Option type="QString" value="solid" name="style"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option type="QString" value="" name="name"/>
                      <Option name="properties"/>
                      <Option type="QString" value="collection" name="type"/>
                    </Option>
                  </data_defined_properties>
                </layer>
              </symbol>
            </background>
            <shadow shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadius="1.5"
                shadowRadiusAlphaOnly="0" shadowOffsetDist="1"
                shadowColor="0,0,0,255" shadowScale="100" shadowOffsetGlobal="1"
                shadowOffsetAngle="135" shadowOffsetUnit="MM" shadowOpacity="0.7"
                shadowDraw="0" shadowBlendMode="6" shadowRadiusUnit="MM"
                shadowRadiusMapUnitScale="3x:0,0,0,0,0,0" shadowUnder="0"/>
            <dd_properties>
              <Option type="Map">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
            </dd_properties>
            <substitutions/>
          </text-style>
          <text-format addDirectionSymbol="0" decimals="3" wrapChar=""
              placeDirectionSymbol="0" leftDirectionSymbol="&lt;"
              formatNumbers="0" autoWrapLength="0" reverseDirectionSymbol="0"
              multilineAlign="3" plussign="0" useMaxLineLengthForAutoWrap="1"
              rightDirectionSymbol=">"/>
          <placement placement="1" preserveRotation="1" polygonPlacementFlags="2"
              centroidInside="0" maxCurvedCharAngleOut="-25" fitInPolygonOnly="0"
              rotationUnit="AngleDegrees" lineAnchorPercent="0.5"
              maxCurvedCharAngleIn="25" lineAnchorTextPoint="FollowPlacement"
              lineAnchorClipping="0" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0"
              offsetType="0" lineAnchorType="0"
              repeatDistanceMapUnitScale="3x:0,0,0,0,0,0"
              predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR"
              dist="2" xOffset="0" overrunDistanceUnit="MM" priority="5"
              distUnits="MM" rotationAngle="0" centroidWhole="0"
              allowDegraded="0" quadOffset="4"
              labelOffsetMapUnitScale="3x:0,0,0,0,0,0" yOffset="0"
              geometryGeneratorEnabled="0" layerType="PointLayer"
              overrunDistance="0" geometryGeneratorType="PointGeometry"
              repeatDistance="0" placementFlags="10" overlapHandling="PreventOverlap"
              repeatDistanceUnits="MM" distMapUnitScale="3x:0,0,0,0,0,0"
              offsetUnits="MM" geometryGenerator=""/>
          <rendering mergeLines="0" scaleVisibility="0" upsidedownLabels="0"
              scaleMin="0" maxNumLabels="2000" scaleMax="0"
              fontMaxPixelSize="10000" drawLabels="1" fontMinPixelSize="0"
              obstacle="1" limitNumLabels="0" obstacleType="1"
              minFeatureSize="0" fontLimitPixelSize="0" obstacleFactor="1"
              unplacedVisibility="0" labelPerPart="0" zIndex="0"/>
          <dd_properties>
            <Option type="Map">
              <Option type="QString" value="" name="name"/>
              <Option type="Map" name="properties">
                <Option type="Map" name="Bold">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN True ELSE False END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Priority">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 10 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 8 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 6 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 4 ELSE 2 END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Show">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="&quot;place&quot; = 'city'" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Size">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 15 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 12 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 10 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 7 ELSE 8 END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="ZIndex">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="coalesce(&quot;population&quot;, 0) / 1000000" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
              </Option>
              <Option type="QString" value="collection" name="type"/>
            </Option>
          </dd_properties>
          <callout type="simple">
            <Option type="Map">
              <Option type="QString" value="pole_of_inaccessibility" name="anchorPoint"/>
              <Option type="int" value="0" name="blendMode"/>
              <Option type="Map" name="ddProperties">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
              <Option type="bool" value="false" name="drawToAllParts"/>
              <Option type="QString" value="0" name="enabled"/>
              <Option type="QString" value="point_on_exterior" name="labelAnchorPoint"/>
              <Option type="QString" value="&lt;symbol type=&quot;line&quot; clip_to_extent=&quot;1&quot; is_animated=&quot;0&quot; frame_rate=&quot;10&quot; alpha=&quot;1&quot; force_rhr=&quot;0&quot; name=&quot;symbol&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;&quot; name=&quot;name&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;collection&quot; name=&quot;type&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer class=&quot;SimpleLine&quot; locked=&quot;0&quot; pass=&quot;0&quot; enabled=&quot;1&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;align_dash_pattern&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;square&quot; name=&quot;capstyle&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;5;2&quot; name=&quot;customdash&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;customdash_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;customdash_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;dash_pattern_offset&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;dash_pattern_offset_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;dash_pattern_offset_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;draw_inside_polygon&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;bevel&quot; name=&quot;joinstyle&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;42,42,42,255&quot; name=&quot;line_color&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;solid&quot; name=&quot;line_style&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0.2&quot; name=&quot;line_width&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;line_width_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;offset&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;offset_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;offset_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;ring_filter&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;trim_distance_end&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_end_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;trim_distance_end_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;trim_distance_start&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_start_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;trim_distance_start_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;tweak_dash_pattern_on_corners&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;use_custom_dash&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;width_map_unit_scale&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;&quot; name=&quot;name&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;collection&quot; name=&quot;type&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" name="lineSymbol"/>
              <Option type="double" value="0" name="minLength"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="minLengthMapUnitScale"/>
              <Option type="QString" value="MM" name="minLengthUnit"/>
              <Option type="double" value="0" name="offsetFromAnchor"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromAnchorMapUnitScale"/>
              <Option type="QString" value="MM" name="offsetFromAnchorUnit"/>
              <Option type="double" value="0" name="offsetFromLabel"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromLabelMapUnitScale"/>
              <Option type="QString" value="MM" name="offsetFromLabelUnit"/>
            </Option>
          </callout>
        </settings>
      </rule>

      <!-- ================================================================
           Rule 2: FEW NEIGHBORS — 1–2 neighbours within 0.2°
           dist = 6 mm, callout enabled
           ================================================================ -->
      <rule description="few neighbors"
            filter="aggregate('places_translated','count',$id,distance($geometry,geometry(@parent))&lt;0.2 AND $id!=attribute(@parent,'fid')) > 0 AND aggregate('places_translated','count',$id,distance($geometry,geometry(@parent))&lt;0.2 AND $id!=attribute(@parent,'fid')) &lt;= 2"
            key="{5e57a92c-57a1-4d5e-8a2b-1c2d3e4f5a6d}">
        <settings calloutType="simple">
          <text-style textColor="42,42,42,255" textOrientation="horizontal"
              fontSizeMapUnitScale="3x:0,0,0,0,0,0" forcedBold="0" fontWeight="50"
              fontSize="8" blendMode="0" textOpacity="1" fontStrikeout="0"
              multilineHeight="1" fontUnderline="0" fontLetterSpacing="0"
              namedStyle="" fontFamily="Trebuchet MS" multilineHeightUnit="Percentage"
              legendString="Aa" capitalization="0" fontWordSpacing="0"
              previewBkgrdColor="255,255,255,255" useSubstitutions="0"
              fontSizeUnit="Point" isExpression="1" fontKerning="1"
              fieldName="concat(if(&quot;name&quot; IS NOT NULL AND &quot;name&quot; != coalesce(&quot;name_eng&quot;, &quot;name:en&quot;, &quot;name:pinyin&quot;, &quot;name&quot;), concat('&lt;span style=&quot;font-size:', to_string(CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 8 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 6 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 5 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 4 ELSE 4 END), 'pt; color:#888888&quot;>', &quot;name&quot;, '&lt;/span>&lt;br>'), ''), coalesce(&quot;name_eng&quot;, &quot;name:en&quot;, &quot;name:pinyin&quot;, &quot;name&quot;))"
              fontItalic="0" allowHtml="1" forcedItalic="0">
            <families/>
            <text-buffer bufferNoFill="1" bufferSizeUnits="MM"
                bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferOpacity="1"
                bufferSize="0.8" bufferColor="255,255,255,255"
                bufferBlendMode="0" bufferDraw="1" bufferJoinStyle="128"/>
            <text-mask maskEnabled="0" maskOpacity="1" maskSizeUnits="MM"
                maskSize="1.5" maskedSymbolLayers="" maskType="0"
                maskJoinStyle="128" maskSizeMapUnitScale="3x:0,0,0,0,0,0"/>
            <background shapeSizeX="0" shapeFillColor="255,255,255,255"
                shapeRadiiY="0" shapeBorderWidthUnit="MM" shapeOffsetX="0"
                shapeSVGFile="" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0"
                shapeBorderColor="128,128,128,255" shapeBorderWidth="0"
                shapeOffsetY="0" shapeJoinStyle="64" shapeRadiiX="0"
                shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeOpacity="1"
                shapeRotationType="0" shapeSizeY="0" shapeDraw="0"
                shapeRotation="0" shapeOffsetUnit="MM" shapeBlendMode="0"
                shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeSizeUnit="MM"
                shapeType="0" shapeSizeType="0"
                shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeRadiiUnit="MM">
              <symbol type="fill" clip_to_extent="1" is_animated="0" frame_rate="10" alpha="1" force_rhr="0" name="fillSymbol">
                <data_defined_properties>
                  <Option type="Map">
                    <Option type="QString" value="" name="name"/>
                    <Option name="properties"/>
                    <Option type="QString" value="collection" name="type"/>
                  </Option>
                </data_defined_properties>
                <layer class="SimpleFill" locked="0" pass="0" enabled="1">
                  <Option type="Map">
                    <Option type="QString" value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale"/>
                    <Option type="QString" value="255,255,255,255" name="color"/>
                    <Option type="QString" value="bevel" name="joinstyle"/>
                    <Option type="QString" value="0,0" name="offset"/>
                    <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
                    <Option type="QString" value="MM" name="offset_unit"/>
                    <Option type="QString" value="128,128,128,255" name="outline_color"/>
                    <Option type="QString" value="no" name="outline_style"/>
                    <Option type="QString" value="0" name="outline_width"/>
                    <Option type="QString" value="MM" name="outline_width_unit"/>
                    <Option type="QString" value="solid" name="style"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option type="QString" value="" name="name"/>
                      <Option name="properties"/>
                      <Option type="QString" value="collection" name="type"/>
                    </Option>
                  </data_defined_properties>
                </layer>
              </symbol>
            </background>
            <shadow shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadius="1.5"
                shadowRadiusAlphaOnly="0" shadowOffsetDist="1"
                shadowColor="0,0,0,255" shadowScale="100" shadowOffsetGlobal="1"
                shadowOffsetAngle="135" shadowOffsetUnit="MM" shadowOpacity="0.7"
                shadowDraw="0" shadowBlendMode="6" shadowRadiusUnit="MM"
                shadowRadiusMapUnitScale="3x:0,0,0,0,0,0" shadowUnder="0"/>
            <dd_properties>
              <Option type="Map">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
            </dd_properties>
            <substitutions/>
          </text-style>
          <text-format addDirectionSymbol="0" decimals="3" wrapChar=""
              placeDirectionSymbol="0" leftDirectionSymbol="&lt;"
              formatNumbers="0" autoWrapLength="0" reverseDirectionSymbol="0"
              multilineAlign="3" plussign="0" useMaxLineLengthForAutoWrap="1"
              rightDirectionSymbol=">"/>
          <placement placement="1" preserveRotation="1" polygonPlacementFlags="2"
              centroidInside="0" maxCurvedCharAngleOut="-25" fitInPolygonOnly="0"
              rotationUnit="AngleDegrees" lineAnchorPercent="0.5"
              maxCurvedCharAngleIn="25" lineAnchorTextPoint="FollowPlacement"
              lineAnchorClipping="0" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0"
              offsetType="0" lineAnchorType="0"
              repeatDistanceMapUnitScale="3x:0,0,0,0,0,0"
              predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR"
              dist="6" xOffset="0" overrunDistanceUnit="MM" priority="5"
              distUnits="MM" rotationAngle="0" centroidWhole="0"
              allowDegraded="0" quadOffset="4"
              labelOffsetMapUnitScale="3x:0,0,0,0,0,0" yOffset="0"
              geometryGeneratorEnabled="0" layerType="PointLayer"
              overrunDistance="0" geometryGeneratorType="PointGeometry"
              repeatDistance="0" placementFlags="10" overlapHandling="PreventOverlap"
              repeatDistanceUnits="MM" distMapUnitScale="3x:0,0,0,0,0,0"
              offsetUnits="MM" geometryGenerator=""/>
          <rendering mergeLines="0" scaleVisibility="0" upsidedownLabels="0"
              scaleMin="0" maxNumLabels="2000" scaleMax="0"
              fontMaxPixelSize="10000" drawLabels="1" fontMinPixelSize="0"
              obstacle="1" limitNumLabels="0" obstacleType="1"
              minFeatureSize="0" fontLimitPixelSize="0" obstacleFactor="1"
              unplacedVisibility="0" labelPerPart="0" zIndex="0"/>
          <dd_properties>
            <Option type="Map">
              <Option type="QString" value="" name="name"/>
              <Option type="Map" name="properties">
                <Option type="Map" name="Bold">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN True ELSE False END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Priority">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 10 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 8 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 6 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 4 ELSE 2 END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Show">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="&quot;place&quot; = 'city'" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Size">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 15 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 12 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 10 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 7 ELSE 8 END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="ZIndex">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="coalesce(&quot;population&quot;, 0) / 1000000" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
              </Option>
              <Option type="QString" value="collection" name="type"/>
            </Option>
          </dd_properties>
          <callout type="simple">
            <Option type="Map">
              <Option type="QString" value="pole_of_inaccessibility" name="anchorPoint"/>
              <Option type="int" value="0" name="blendMode"/>
              <Option type="Map" name="ddProperties">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
              <Option type="bool" value="false" name="drawToAllParts"/>
              <Option type="QString" value="1" name="enabled"/>
              <Option type="QString" value="point_on_exterior" name="labelAnchorPoint"/>
              <Option type="QString" value="&lt;symbol type=&quot;line&quot; clip_to_extent=&quot;1&quot; is_animated=&quot;0&quot; frame_rate=&quot;10&quot; alpha=&quot;1&quot; force_rhr=&quot;0&quot; name=&quot;symbol&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;&quot; name=&quot;name&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;collection&quot; name=&quot;type&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer class=&quot;SimpleLine&quot; locked=&quot;0&quot; pass=&quot;0&quot; enabled=&quot;1&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;align_dash_pattern&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;square&quot; name=&quot;capstyle&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;5;2&quot; name=&quot;customdash&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;customdash_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;customdash_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;dash_pattern_offset&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;dash_pattern_offset_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;dash_pattern_offset_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;draw_inside_polygon&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;bevel&quot; name=&quot;joinstyle&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;42,42,42,255&quot; name=&quot;line_color&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;solid&quot; name=&quot;line_style&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0.2&quot; name=&quot;line_width&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;line_width_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;offset&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;offset_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;offset_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;ring_filter&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;trim_distance_end&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_end_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;trim_distance_end_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;trim_distance_start&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_start_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;trim_distance_start_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;tweak_dash_pattern_on_corners&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;use_custom_dash&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;width_map_unit_scale&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;&quot; name=&quot;name&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;collection&quot; name=&quot;type&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" name="lineSymbol"/>
              <Option type="double" value="0" name="minLength"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="minLengthMapUnitScale"/>
              <Option type="QString" value="MM" name="minLengthUnit"/>
              <Option type="double" value="0" name="offsetFromAnchor"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromAnchorMapUnitScale"/>
              <Option type="QString" value="MM" name="offsetFromAnchorUnit"/>
              <Option type="double" value="0" name="offsetFromLabel"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromLabelMapUnitScale"/>
              <Option type="QString" value="MM" name="offsetFromLabelUnit"/>
            </Option>
          </callout>
        </settings>
      </rule>

      <!-- ================================================================
           Rule 3: CROWDED — >2 neighbours within 0.2°
           dist = 16 mm, callout enabled
           ================================================================ -->
      <rule description="crowded"
            filter="aggregate('places_translated','count',$id,distance($geometry,geometry(@parent))&lt;0.2 AND $id!=attribute(@parent,'fid')) > 2"
            key="{5e57a92c-57a1-4d5e-8a2b-1c2d3e4f5a6e}">
        <settings calloutType="simple">
          <text-style textColor="42,42,42,255" textOrientation="horizontal"
              fontSizeMapUnitScale="3x:0,0,0,0,0,0" forcedBold="0" fontWeight="50"
              fontSize="8" blendMode="0" textOpacity="1" fontStrikeout="0"
              multilineHeight="1" fontUnderline="0" fontLetterSpacing="0"
              namedStyle="" fontFamily="Trebuchet MS" multilineHeightUnit="Percentage"
              legendString="Aa" capitalization="0" fontWordSpacing="0"
              previewBkgrdColor="255,255,255,255" useSubstitutions="0"
              fontSizeUnit="Point" isExpression="1" fontKerning="1"
              fieldName="concat(if(&quot;name&quot; IS NOT NULL AND &quot;name&quot; != coalesce(&quot;name_eng&quot;, &quot;name:en&quot;, &quot;name:pinyin&quot;, &quot;name&quot;), concat('&lt;span style=&quot;font-size:', to_string(CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 8 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 6 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 5 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 4 ELSE 4 END), 'pt; color:#888888&quot;>', &quot;name&quot;, '&lt;/span>&lt;br>'), ''), coalesce(&quot;name_eng&quot;, &quot;name:en&quot;, &quot;name:pinyin&quot;, &quot;name&quot;))"
              fontItalic="0" allowHtml="1" forcedItalic="0">
            <families/>
            <text-buffer bufferNoFill="1" bufferSizeUnits="MM"
                bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferOpacity="1"
                bufferSize="0.8" bufferColor="255,255,255,255"
                bufferBlendMode="0" bufferDraw="1" bufferJoinStyle="128"/>
            <text-mask maskEnabled="0" maskOpacity="1" maskSizeUnits="MM"
                maskSize="1.5" maskedSymbolLayers="" maskType="0"
                maskJoinStyle="128" maskSizeMapUnitScale="3x:0,0,0,0,0,0"/>
            <background shapeSizeX="0" shapeFillColor="255,255,255,255"
                shapeRadiiY="0" shapeBorderWidthUnit="MM" shapeOffsetX="0"
                shapeSVGFile="" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0"
                shapeBorderColor="128,128,128,255" shapeBorderWidth="0"
                shapeOffsetY="0" shapeJoinStyle="64" shapeRadiiX="0"
                shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeOpacity="1"
                shapeRotationType="0" shapeSizeY="0" shapeDraw="0"
                shapeRotation="0" shapeOffsetUnit="MM" shapeBlendMode="0"
                shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeSizeUnit="MM"
                shapeType="0" shapeSizeType="0"
                shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeRadiiUnit="MM">
              <symbol type="fill" clip_to_extent="1" is_animated="0" frame_rate="10" alpha="1" force_rhr="0" name="fillSymbol">
                <data_defined_properties>
                  <Option type="Map">
                    <Option type="QString" value="" name="name"/>
                    <Option name="properties"/>
                    <Option type="QString" value="collection" name="type"/>
                  </Option>
                </data_defined_properties>
                <layer class="SimpleFill" locked="0" pass="0" enabled="1">
                  <Option type="Map">
                    <Option type="QString" value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale"/>
                    <Option type="QString" value="255,255,255,255" name="color"/>
                    <Option type="QString" value="bevel" name="joinstyle"/>
                    <Option type="QString" value="0,0" name="offset"/>
                    <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
                    <Option type="QString" value="MM" name="offset_unit"/>
                    <Option type="QString" value="128,128,128,255" name="outline_color"/>
                    <Option type="QString" value="no" name="outline_style"/>
                    <Option type="QString" value="0" name="outline_width"/>
                    <Option type="QString" value="MM" name="outline_width_unit"/>
                    <Option type="QString" value="solid" name="style"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option type="QString" value="" name="name"/>
                      <Option name="properties"/>
                      <Option type="QString" value="collection" name="type"/>
                    </Option>
                  </data_defined_properties>
                </layer>
              </symbol>
            </background>
            <shadow shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadius="1.5"
                shadowRadiusAlphaOnly="0" shadowOffsetDist="1"
                shadowColor="0,0,0,255" shadowScale="100" shadowOffsetGlobal="1"
                shadowOffsetAngle="135" shadowOffsetUnit="MM" shadowOpacity="0.7"
                shadowDraw="0" shadowBlendMode="6" shadowRadiusUnit="MM"
                shadowRadiusMapUnitScale="3x:0,0,0,0,0,0" shadowUnder="0"/>
            <dd_properties>
              <Option type="Map">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
            </dd_properties>
            <substitutions/>
          </text-style>
          <text-format addDirectionSymbol="0" decimals="3" wrapChar=""
              placeDirectionSymbol="0" leftDirectionSymbol="&lt;"
              formatNumbers="0" autoWrapLength="0" reverseDirectionSymbol="0"
              multilineAlign="3" plussign="0" useMaxLineLengthForAutoWrap="1"
              rightDirectionSymbol=">"/>
          <placement placement="1" preserveRotation="1" polygonPlacementFlags="2"
              centroidInside="0" maxCurvedCharAngleOut="-25" fitInPolygonOnly="0"
              rotationUnit="AngleDegrees" lineAnchorPercent="0.5"
              maxCurvedCharAngleIn="25" lineAnchorTextPoint="FollowPlacement"
              lineAnchorClipping="0" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0"
              offsetType="0" lineAnchorType="0"
              repeatDistanceMapUnitScale="3x:0,0,0,0,0,0"
              predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR"
              dist="16" xOffset="0" overrunDistanceUnit="MM" priority="5"
              distUnits="MM" rotationAngle="0" centroidWhole="0"
              allowDegraded="0" quadOffset="4"
              labelOffsetMapUnitScale="3x:0,0,0,0,0,0" yOffset="0"
              geometryGeneratorEnabled="0" layerType="PointLayer"
              overrunDistance="0" geometryGeneratorType="PointGeometry"
              repeatDistance="0" placementFlags="10" overlapHandling="PreventOverlap"
              repeatDistanceUnits="MM" distMapUnitScale="3x:0,0,0,0,0,0"
              offsetUnits="MM" geometryGenerator=""/>
          <rendering mergeLines="0" scaleVisibility="0" upsidedownLabels="0"
              scaleMin="0" maxNumLabels="2000" scaleMax="0"
              fontMaxPixelSize="10000" drawLabels="1" fontMinPixelSize="0"
              obstacle="1" limitNumLabels="0" obstacleType="1"
              minFeatureSize="0" fontLimitPixelSize="0" obstacleFactor="1"
              unplacedVisibility="0" labelPerPart="0" zIndex="0"/>
          <dd_properties>
            <Option type="Map">
              <Option type="QString" value="" name="name"/>
              <Option type="Map" name="properties">
                <Option type="Map" name="Bold">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN True ELSE False END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Priority">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 10 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 8 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 6 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 4 ELSE 2 END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Show">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="&quot;place&quot; = 'city'" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="Size">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="CASE WHEN coalesce(&quot;population&quot;, 0) >= 5000000 THEN 15 WHEN coalesce(&quot;population&quot;, 0) >= 1000000 THEN 12 WHEN coalesce(&quot;population&quot;, 0) >= 500000 THEN 10 WHEN coalesce(&quot;population&quot;, 0) >= 100000 THEN 7 ELSE 8 END" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
                <Option type="Map" name="ZIndex">
                  <Option type="bool" value="true" name="active"/>
                  <Option type="QString" value="coalesce(&quot;population&quot;, 0) / 1000000" name="expression"/>
                  <Option type="int" value="3" name="type"/>
                </Option>
              </Option>
              <Option type="QString" value="collection" name="type"/>
            </Option>
          </dd_properties>
          <callout type="simple">
            <Option type="Map">
              <Option type="QString" value="pole_of_inaccessibility" name="anchorPoint"/>
              <Option type="int" value="0" name="blendMode"/>
              <Option type="Map" name="ddProperties">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
              <Option type="bool" value="false" name="drawToAllParts"/>
              <Option type="QString" value="1" name="enabled"/>
              <Option type="QString" value="point_on_exterior" name="labelAnchorPoint"/>
              <Option type="QString" value="&lt;symbol type=&quot;line&quot; clip_to_extent=&quot;1&quot; is_animated=&quot;0&quot; frame_rate=&quot;10&quot; alpha=&quot;1&quot; force_rhr=&quot;0&quot; name=&quot;symbol&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;&quot; name=&quot;name&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;collection&quot; name=&quot;type&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer class=&quot;SimpleLine&quot; locked=&quot;0&quot; pass=&quot;0&quot; enabled=&quot;1&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;align_dash_pattern&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;square&quot; name=&quot;capstyle&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;5;2&quot; name=&quot;customdash&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;customdash_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;customdash_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;dash_pattern_offset&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;dash_pattern_offset_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;dash_pattern_offset_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;draw_inside_polygon&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;bevel&quot; name=&quot;joinstyle&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;42,42,42,255&quot; name=&quot;line_color&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;solid&quot; name=&quot;line_style&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0.2&quot; name=&quot;line_width&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;line_width_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;offset&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;offset_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;offset_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;ring_filter&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;trim_distance_end&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_end_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;trim_distance_end_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;trim_distance_start&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_start_map_unit_scale&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;MM&quot; name=&quot;trim_distance_start_unit&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;tweak_dash_pattern_on_corners&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;0&quot; name=&quot;use_custom_dash&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;width_map_unit_scale&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option type=&quot;QString&quot; value=&quot;&quot; name=&quot;name&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option type=&quot;QString&quot; value=&quot;collection&quot; name=&quot;type&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" name="lineSymbol"/>
              <Option type="double" value="0" name="minLength"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="minLengthMapUnitScale"/>
              <Option type="QString" value="MM" name="minLengthUnit"/>
              <Option type="double" value="0" name="offsetFromAnchor"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromAnchorMapUnitScale"/>
              <Option type="QString" value="MM" name="offsetFromAnchorUnit"/>
              <Option type="double" value="0" name="offsetFromLabel"/>
              <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromLabelMapUnitScale"/>
              <Option type="QString" value="MM" name="offsetFromLabelUnit"/>
            </Option>
          </callout>
        </settings>
      </rule>

    </rules>
  </labeling>
</qgis>
