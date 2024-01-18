import llnl.util.tty as tty

_supported_suites = {
    "art": "cetlib_except cetlib fhiclcpp messagefacility hep_concurrency canvas art",
    "artdaq": "artdaq_core artdaq_core_demo artdaq_utilities artdaq_ganglia_plugin artdaq_epics_plugin artdaq_database artdaq_daqinterface artdaq_mpich_plugin artdaq_mfextensions",
    "critic": "cetlib_except cetlib hep_concurrency fhiclcpp messagefacility canvas canvas_root_io art art_root_io gallery critic",
    "dune": "dunecore duneopdet dunesim dunecalib duneprototypes dunedataprep dunereco duneana duneexamples dunesw duneutil protoduneana",
    "gallery": "cetlib_except cetlib hep_concurrency fhiclcpp messagefacility canvas canvas_root_io fhiclpy gallery",
    "larsoft": "larcore lardata larevt larsim larsimrad larsimdnn larg4 larreco larrecodnn larana larexamples lareventdisplay larpandora larfinder larwirecell larsoft",
    "larsoftobj": "larcoreobj lardataobj larcorealg lardataalg larvecutils larsoftobj",
    "nu": "nusimdata nuevdb nug4 nugen nurandom nufinder nutools",
    "sbn": "sbncode sbnobj sbnanaobj sbndcode sbndutil icaruscode icarusutil icarusalg icarus_signal_processing sbnci",
    "sbndaq": "sbndaq sbndaq_artdaq sbndaq_artdaq_core sbndaq_xporter sbndaq_minargon sbndaq_online sbndaq_decode",
    "uboone": "uboonecode ubutil uboonedata ublite ubana ubreco ubsim ubevt ubraw ubcrt ubcore ubcv ubobj",
}


def help_suites():
    print()
    tty.msg("Supported suites:\n")
    title = "Suite"
    suite_width = max(len(s) for s in _supported_suites.keys())
    print(f"  {title:<{suite_width}}  Repositories")
    print("  " + "-" * 100)
    for suite, repositories in _supported_suites.items():
        print(f"  {suite:<{suite_width}}  {repositories}")
    print()
