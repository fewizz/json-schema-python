class Resolver:

    def __init__(self):
        self.contents_by_abs_uri = dict[str, dict | bool]()

    def resolve(self, uri: str):
        if "#" in uri:
            raise RuntimeError()
        return self.contents_by_abs_uri[uri]
