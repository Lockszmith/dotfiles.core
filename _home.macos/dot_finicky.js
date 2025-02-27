// Use https://finicky-kickstart.now.sh to generate basic configuration
// Learn more about configuration options: https://github.com/johnste/finicky/wiki/Configuration

module.exports = {
  defaultBrowser: "Browserosaurus",
  rewrite: [{
    match: () => true, // Execute rewrite on all incoming urls to make this example easier to understand
    url: ({ url }) => {
      const removeKeysStartingWith = ["utm_", "uta_"]; // Remove all query parameters beginning with these strings
      const removeKeys = ["fbclid", "gclid", "si"]; // Remove all query parameters matching these keys

      const search = url.search
        .split("&")
        .map((parameter) => parameter.split("="))
        .filter(([key]) => !removeKeysStartingWith.some((startingWith) => key.startsWith(startingWith)))
        .filter(([key]) => !removeKeys.some((removeKey) => key === removeKey));

      return {
        ...url,
        search: search.map((parameter) => parameter.join("=")).join("&"),
      };
    },
  }],
  handlers: [
    {
      match: [
        finicky.matchDomains(/.*\.vastdata.com/),
        "deeplinks.mindtickle.com*",
        //"vastdata.mindtickle.com*",
        "vastdata.*"
      ],
      browser: "Google Chrome"
    },
    {
      match: [
        finicky.matchDomains(/127\.0\.0\.1/)
      ],
      browser: "DuckDuckGo"
    },
    {
      // Open these in Browserosaurus
      match: [
        "github.com*",
        "open.spotify.com*",
        // YouTube
        "youtube.com*",
        "youtu.be*",
        finicky.matchDomains(/.*\.youtube.com/) // use helper function to match on domain only
      ],
      browser: "Browserosaurus"
    }
  ]
}
