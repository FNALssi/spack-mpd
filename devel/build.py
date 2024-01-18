import subprocess


def build(srcs, build_area, generator, parallel, generator_options):
    configure_list = ["cmake", "--preset", "default", srcs, "-B", build_area]
    if generator:
        configure_list += ["-G", generator]
    subprocess.run(configure_list)

    generator_list = ["--"]
    if parallel:
        generator_list.append(f"-j{parallel}")
    if generator_options:
        generator_list += generator_options

    subprocess.run(["cmake", "--build", build_area] + generator_list)
