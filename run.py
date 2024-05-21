from app import create_app
from OpenSSL import SSL

app = create_app()

if __name__ == "__main__":
    context = SSL.Context(SSL.SSLv23_METHOD)
    context.use_privatekey_file('/etc/ssl/private/fm_server.key')
    context.use_certificate_file('/etc/ssl/certs/fm_server.crt')
    context.load_verify_locations('/etc/ssl/certs/ca.pem')
    context.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT, lambda conn, cert, errno, depth, ok: ok)
    app.run(host='0.0.0.0', debug=True)
