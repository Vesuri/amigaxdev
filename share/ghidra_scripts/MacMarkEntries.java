// Mark the loader/init/interrupt entry points and disassemble from each so
// auto-analysis can follow control flow.  The entry list is the project's
// ghidra_scripts/entrypoints.csv (see run() for the lookup); a project may generate rows of it (e.g. from the CODE 0 jump table),
// never transcribed into this script or hand-edited.
//@category AmigaXDev
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import ghidra.app.script.GhidraScript;
import generic.jar.ResourceFile;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class MacMarkEntries extends GhidraScript {
    private static final Pattern SEGMENT_ID = Pattern.compile("CODE_(\\d+)");

    @Override
    public void run() throws Exception {
        // The project's list: $AMIGA_GHIDRA_ENTRYPOINTS, else ghidra_scripts/entrypoints.csv
        // below the directory Ghidra was started from (the project root), else next to the
        // script (a project's own copy of it).
        String fromEnv = System.getenv("AMIGA_GHIDRA_ENTRYPOINTS");
        ResourceFile csv = fromEnv != null && !fromEnv.isEmpty()
            ? new ResourceFile(new File(fromEnv))
            : new ResourceFile(new File("ghidra_scripts", "entrypoints.csv").getAbsoluteFile());
        if (!csv.exists()) {
            csv = new ResourceFile(getSourceFile().getParentFile(), "entrypoints.csv");
        }
        if (!csv.exists()) {
            printerr("MacMarkEntries: entrypoints.csv not found ($AMIGA_GHIDRA_ENTRYPOINTS, "
                + "ghidra_scripts/ in the current directory, or next to the script)");
            return;
        }
        Matcher programSegment = SEGMENT_ID.matcher(currentProgram.getName());
        int currentSegment = programSegment.find() ? Integer.parseInt(programSegment.group(1)) : -1;
        int marked = 0, promoted = 0, skipped = 0, otherSegment = 0;
        try (BufferedReader r = new BufferedReader(new InputStreamReader(csv.getInputStream()))) {
            String line;
            while ((line = r.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                String[] fields = line.split(",", 4);
                if (fields.length < 2) { printerr("MacMarkEntries: bad line: " + line); continue; }
                String hex;
                String name;
                // Current format: segment,addr,name,note.  Keep accepting the
                // original addr,name,note rows for hand-added local roots.
                if (fields[0].trim().equalsIgnoreCase("segment")) continue;
                if (fields[0].trim().equalsIgnoreCase("addr")) continue;
                if (fields.length >= 3 && fields[0].trim().matches("[0-9]+")) {
                    int rowSegment = Integer.parseInt(fields[0].trim());
                    if (currentSegment >= 0 && rowSegment != currentSegment) {
                        otherSegment++;
                        continue;
                    }
                    hex = fields[1].trim();
                    name = fields[2].trim();
                } else {
                    hex = fields[0].trim();
                    name = fields[1].trim();
                }
                if (hex.startsWith("0x") || hex.startsWith("0X")) hex = hex.substring(2);
                if (hex.startsWith("$")) hex = hex.substring(1);
                long addrVal;
                try {
                    addrVal = Long.parseLong(hex, 16);
                } catch (NumberFormatException e) {
                    printerr("MacMarkEntries: bad address '" + hex + "' on line: " + line);
                    continue;
                }
                Address a = toAddr(addrVal);
                addEntryPoint(a);
                disassemble(a);
                Function existing = getFunctionAt(a);
                if (existing == null) {
                    createFunction(a, name);
                    println("entry: " + name + " @ " + a);
                    marked++;
                } else {
                    if (existing.getSymbol().getSource() == SourceType.ANALYSIS
                            || existing.getSymbol().getSource() == SourceType.DEFAULT) {
                        existing.setName(name, SourceType.USER_DEFINED);
                        println("entry (promoted): " + name + " @ " + a);
                        promoted++;
                    } else {
                        println("entry (exists): " + existing.getName() + " @ " + a);
                        skipped++;
                    }
                }
            }
        }
        println("MacMarkEntries: segment " + currentSegment + ": " + marked + " new, "
            + promoted + " promoted from analysis, " + skipped + " already-present; "
            + otherSegment + " rows belonged to other segments.");
    }
}
