import React from 'react'

export default {
  logo: <span>VideoLingo-Freelancer</span>,
  project: {
    link: 'https://github.com/jcxl8/VideoLingo-freelancer',
  },
  docsRepositoryBase: 'https://github.com/jcxl8/VideoLingo-freelancer/tree/main/docs',
  footer: {
    text: 'VideoLingo-Freelancer',
  },
  useNextSeoProps() {
    return {
      titleTemplate: '%s – VideoLingo-Freelancer',
    }
  },
}
