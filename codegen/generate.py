import build_info
import grpc_bindings
import stub_api

if __name__ == "__main__":
    build_info.generate()
    grpc_bindings.generate()
    stub_api.generate()
