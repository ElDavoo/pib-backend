{
  description = "PIB telemetry ingestion backend";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python312.withPackages (ps: with ps; [
            fastapi
            httpx
            pydantic
            pytest
            uvicorn
          ]);
        in
        {
          default = pkgs.mkShell {
            packages = [ python pkgs.sqlite ];
          };
        });
    };
}
