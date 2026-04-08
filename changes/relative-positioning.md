bump: minor
Added relative motion translations (translate/from_translate with normalized multipliers) as the preferred approach for move and move-to animations; absolute pixel offset fields (offset_x/y, from_offset_x/y) are retained for backwards compatibility; the unused absolute layout mode is removed from the DSL surface.
