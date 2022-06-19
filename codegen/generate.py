import grpc_bindings
import stub_api

if __name__ == "__main__":
    grpc_bindings.generate()
    stub_api.generate()
